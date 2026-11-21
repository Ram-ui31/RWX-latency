"""Experimental differential initialization for literal class-data edits."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import resource
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
from research.state_diff.eligibility import literal_assignment


def refine(source, text, selected, tests, index, readers, baseline, inventory, timeout):
    edits = parse_patch(text)
    if len(edits) != 1:
        return selected, "one_file_only"
    edit = edits[0]
    path = edit.old_path
    info = index.payload["files"].get(path)
    if path != edit.new_path or not info or not path.startswith("sqlglot/"):
        return selected, "unsupported_source"
    old = info["source"]
    key = literal_assignment(old, apply_change(old, edit))
    if key is None:
        return selected, "literal_assignment_only"
    owner = path + "#" + key.rsplit(".", 1)[0] + "."
    if any(k.startswith(owner) for k in baseline["opaque"]):
        return selected, "opaque_owner"
    with PatchedTree(source, text) as tree:
        result = tree.path.parent / "state.json"
        proc = subprocess.run(
            [sys.executable, "-B", str(Path(__file__).with_name("snapshot.py")),
             "--source", str(tree.path), "--inventory", str(inventory),
             "--output", str(result)],
            env=dict(os.environ, PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1"),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout,
        )
        if proc.returncode or not result.exists():
            return selected, "import_failed"
        after = json.loads(result.read_text())
    if after["opaque"] != baseline["opaque"]:
        return selected, "opaque_state_changed"
    changed = {k for k in baseline["states"].keys() | after["states"].keys()
               if baseline["states"].get(k) != after["states"].get(k)}
    if any(k.startswith(owner) for k in after["opaque"]):
        return selected, "opaque_owner"
    retained = selected - index.map_ids(readers["passed"])
    retained.update(index.unobserved & selected)
    retained.update(index.map_ids(index.payload["reads"].get(path, [])) & selected)
    for item in changed:
        attribute = item.split("#", 1)[1].rsplit(".", 1)[-1]
        # Unrecorded attribute kinds cannot justify omission.
        if not (attribute.isupper() or attribute in {"arg_types", "required_args"}):
            return selected, "untracked_derived_attribute"
        retained.update(index.map_ids(readers["consumers"].get(item, [])) & selected)
        for test in ([] if readers.get("test_code_instrumented") else tests):
            test_source = index.payload["files"].get(test["file"], {}).get("source")
            if test_source is None:
                return selected, "test_source_missing"
            if (attribute in test_source or any(x in test_source for x in (
                    "getattr", "vars(", "__dict__", "getmembers"))):
                if test["number"] in selected:
                    retained.add(test["number"])
    return retained, "initialized_state_readers"


def main():
    parser = argparse.ArgumentParser()
    for name in ("source", "data", "baseline", "readers", "inventory", "upstream", "output", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--budget", type=float, default=15)
    args = parser.parse_args()
    tests, ids, durations = load_catalog(args.data / "tests.json")
    index = SourceIndex(ROOT / "maps/source-index.json.gz", ids)
    baseline = json.loads(args.baseline.read_text())
    readers = json.loads(gzip.decompress(args.readers.read_bytes()))
    rows = list(map(json.loads, args.upstream.read_text().splitlines()))
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.process_time()
    def cpu():
        used = resource.getrusage(resource.RUSAGE_CHILDREN)
        return time.process_time() - started + used.ru_utime + used.ru_stime - before.ru_utime - before.ru_stime
    observations = []
    for row in rows:
        selected = set(sum(row["workers"], []))
        if not selected or cpu() >= args.budget:
            continue
        tick = cpu()
        try:
            refined, reason = refine(
                args.source, (args.data / "commits" / (row["commit"] + ".patch")).read_text(),
                selected, tests, index, readers, baseline, args.inventory, 5)
        except (ValueError, OSError, subprocess.TimeoutExpired):
            refined, reason = selected, "unresolved"
        old_cost = schedule_cost(row["workers"], durations) / 1000
        row["workers"] = optimize_schedule(refined, durations)
        observations.append(dict(commit=row["commit"],reason=reason,removed=len(selected-refined),
                                 cpu=cpu()-tick,saving=old_cost-schedule_cost(row["workers"],durations)/1000))
    args.output.write_text("".join(json.dumps(r)+"\n" for r in rows))
    args.report.write_text(json.dumps(dict(cpu=cpu(),actions=observations),indent=2))


if __name__ == "__main__":
    main()
