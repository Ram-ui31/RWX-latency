"""Cost-gated original integration checks with baseline native SELECT memoization."""

import argparse
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from blast.catalog import load_catalog
from blast.patches import parse_patch, apply_change
from blast.selection import SourceIndex
from blast.scheduling import optimize_schedule, schedule_cost
from engine.runner import PatchedTree
from engine.source_origin import verify
from engine.verification_budget import gate
from research.native_oracle.common import environment, sha
from research.state_diff.choose import ArgumentContracts, boolean_edit


def main():
    parser = argparse.ArgumentParser()
    for key in (
        "source",
        "data",
        "cache",
        "contracts",
        "readers",
        "upstream",
        "output",
        "report",
    ):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--selection-report", type=Path)
    parser.add_argument("--budget", type=float, default=20)
    parser.add_argument("--wall-budget", type=float, default=30)
    args = parser.parse_args()
    verify(args.source)
    started = time.process_time()
    wall = time.monotonic()
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)

    def cpu():
        used = resource.getrusage(resource.RUSAGE_CHILDREN)
        return (
            time.process_time()
            - started
            + used.ru_utime
            + used.ru_stime
            - usage.ru_utime
            - usage.ru_stime
        )

    manifest = json.loads(Path(str(args.cache) + ".json").read_text())
    if (
        manifest.get("baseline_status") != "observed_pass"
        or manifest["environment"] != environment()
        or manifest.get("unsafe_queries")
        or sha(args.cache) != manifest["sha256"]
    ):
        raise ValueError("uncertified native reference cache")
    tests, ids, durations = load_catalog(args.data / "tests.json")
    index = SourceIndex(ROOT / "maps/source-index.json.gz", ids)
    contract = ArgumentContracts(args.contracts, args.readers, index)
    target = ids["tests/test_executor.py::TestExecutor::test_execute_tpcds"]
    rows = list(map(json.loads, args.upstream.read_text().splitlines()))
    decisions = []
    metadata = (
        json.loads(args.selection_report.read_text())["patches"]
        if args.selection_report
        else {}
    )
    for row in rows:
        selected = set(sum(row["workers"], []))
        if target not in selected or metadata.get(row["commit"], {}).get(
            "import_hazard"
        ):
            continue
        text = (args.data / "commits" / (row["commit"] + ".patch")).read_text()
        edits = parse_patch(text)
        if len(edits) != 1:
            continue
        edit = edits[0]
        info = index.payload["files"].get(edit.old_path)
        if not info or edit.old_path != edit.new_path:
            continue
        parsed = boolean_edit(info["source"], apply_change(info["source"], edit))
        if (
            parsed is None
            or edit.old_path + "#" + parsed[0] + ":" + parsed[1][0]
            not in contract.payload["edges"]
        ):
            continue
        contract.narrow(text, selected)
        if contract.import_hazard:
            continue
        before = schedule_cost(row["workers"], durations) / 1000
        after = (
            schedule_cost(optimize_schedule(selected - {target}, durations), durations)
            / 1000
        )
        gain = before - after
        decision = gate(
            gain,
            args.budget - cpu(),
            dict(
                status="observed_pass",
                total_cpu_seconds=manifest["baseline_cpu_seconds"],
            ),
        )
        if not decision["allowed"] or time.monotonic() - wall >= args.wall_budget:
            continue
        tick = cpu()
        evidence = {"status": "unresolved"}
        with PatchedTree(args.source, text) as tree:
            result = tree.path.parent / "memo-result.json"
            timeout = min(
                25,
                max(0.01, (args.budget - cpu()) / 2),
                max(0.01, args.wall_budget - (time.monotonic() - wall)),
            )
            with tempfile.TemporaryFile() as logs:
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-B",
                        str(Path(__file__).with_name("worker.py")),
                        "--source",
                        str(tree.path),
                        "--cache",
                        str(args.cache.resolve()),
                        "--result",
                        str(result),
                    ],
                    cwd=tree.path,
                    env=dict(
                        os.environ,
                        PYTHON_CPU_COUNT="2",
                        SKIP_INTEGRATION="0",
                        PYTHONDONTWRITEBYTECODE="1",
                        PATH=str(Path(sys.executable).parent)
                        + os.pathsep
                        + os.environ["PATH"],
                    ),
                    stdout=logs,
                    stderr=logs,
                    start_new_session=True,
                )
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            if process.returncode == 0 and result.exists():
                evidence = json.loads(result.read_text())
        if evidence["status"] == "observed_pass":
            selected.remove(target)
            row["workers"] = optimize_schedule(selected, durations)
        decisions.append(
            dict(
                commit=row["commit"],
                cpu=cpu() - tick,
                potential_saving=gain,
                saving=before - schedule_cost(row["workers"], durations) / 1000,
                **evidence
            )
        )
    args.output.write_text("".join(json.dumps(row) + "\n" for row in rows))
    report = dict(stage="native_reference_memo", cpu=cpu(), actions=decisions)
    args.report.write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
