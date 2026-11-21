"""Budgeted original pytest groups. Keeps failed, skipped and incomplete tests."""

import argparse, json, os, resource, signal, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from engine.runner import PatchedTree
from blast.catalog import load_catalog
from blast.scheduling import optimize_schedule, schedule_cost

PLUGIN = """
import json,os
reports=[]
def pytest_runtest_logreport(report):
 reports.append(dict(nodeid=report.nodeid,when=report.when,outcome=report.outcome))
 with open(os.environ['RWX_GROUP_RESULT'],'w') as f:json.dump(reports,f)
"""


def run_group(source, text, nodes, timeout, minimal=False, warm=False):
    with PatchedTree(source, text) as tree:
        plugin = tree.path.parent / "rwx_group_plugin.py"
        plugin.write_text(PLUGIN)
        result = tree.path.parent / "group.json"
        env = dict(
            os.environ,
            SKIP_INTEGRATION="0",
            PYTHONDONTWRITEBYTECODE="1",
            PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
            RWX_GROUP_RESULT=str(result),
            PYTHONPATH=str(plugin.parent) + os.pathsep + str(tree.path),
            HOME=str(tree.path.parent),
        )
        args = [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "-p",
            "rwx_group_plugin",
            "-p",
            "pytest_timeout",
            "-p",
            "no:cacheprovider",
            "-q",
            *nodes,
        ]
        if minimal:
            inventory = tree.path.parent / "nodes.json"
            inventory.write_text(json.dumps(nodes))
            args = [
                sys.executable,
                "-B",
                str(Path(__file__).with_name("minimal.py")),
                "--source",
                str(tree.path),
                "--nodes",
                str(inventory),
                "--result",
                str(result),
            ]
            env["PYTHON_CPU_COUNT"] = "2"
        if warm:
            from research.group_verifier.minimal import execute

            with tempfile_logs() as logs:
                pid = os.fork()
                if pid == 0:
                    try:
                        os.setsid()
                        os.environ.update(env)
                        os.chdir(tree.path)
                        os.dup2(logs.fileno(), 1)
                        os.dup2(logs.fileno(), 2)
                        execute(tree.path, nodes, result)
                        os._exit(0)
                    except BaseException:
                        os._exit(2)
                deadline = time.monotonic() + timeout
                status = None
                while time.monotonic() < deadline:
                    done, status = os.waitpid(pid, os.WNOHANG)
                    if done:
                        break
                    time.sleep(0.01)
                else:
                    try:
                        os.killpg(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    os.waitpid(pid, 0)
                    return set()
                if status != 0 or not result.exists():
                    return set()
                return set(json.loads(result.read_text())["passed"])
        with tempfile_logs() as logs:
            proc = subprocess.Popen(
                args,
                cwd=tree.path,
                env=env,
                stdout=logs,
                stderr=logs,
                start_new_session=True,
            )
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
        # A terminated group can corrupt lifecycle obligations. Trust only completed sessions.
        if proc.returncode not in (0, 1) or not result.exists():
            return set()
        if minimal:
            return set(json.loads(result.read_text())["passed"])
        rows = json.loads(result.read_text())
        passed = set()
        for node in nodes:
            seen = [r for r in rows if r["nodeid"] == node]
            if (
                seen
                and all(r["outcome"] == "passed" for r in seen)
                and {"setup", "call", "teardown"} <= {r["when"] for r in seen}
            ):
                passed.add(node)
        # Setup/teardown errors on a broader node invalidate this group's reuse.
        if any(r["outcome"] == "failed" and r["when"] != "call" for r in rows):
            return set()
        return passed


def tempfile_logs():
    import tempfile

    return tempfile.TemporaryFile()


def main():
    ap = argparse.ArgumentParser()
    for k in ("source", "data", "upstream", "output", "report"):
        ap.add_argument("--" + k, type=Path, required=True)
    ap.add_argument("--budget", type=float, default=30)
    ap.add_argument("--wall-budget", type=float, default=100)
    ap.add_argument("--seconds-factor", type=float, default=1.5)
    ap.add_argument("--minimal", action="store_true")
    ap.add_argument("--warm-fork", action="store_true")
    ap.add_argument("--cheap-modules", action="store_true")
    ap.add_argument("--cost-profile", type=Path)
    ap.add_argument("--selection-report", type=Path)
    a = ap.parse_args()
    tests, ids, ds = load_catalog(a.data / "tests.json")
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.process_time()
    wall = time.monotonic()

    def cpu():
        r = resource.getrusage(resource.RUSAGE_CHILDREN)
        return (
            time.process_time()
            - start
            + r.ru_utime
            + r.ru_stime
            - before.ru_utime
            - before.ru_stime
        )

    if a.warm_fork:
        import numpy, pandas, duckdb

        if any(
            n == "sqlglot" or n.startswith(("sqlglot.", "tests.")) for n in sys.modules
        ):
            raise ValueError("warm parent contains application code")
    rows = list(map(json.loads, a.upstream.read_text().splitlines()))
    report = []
    selection_report = (
        json.loads(a.selection_report.read_text())["patches"]
        if a.selection_report
        else {}
    )
    profile = None
    if a.cost_profile:
        from research.observations.capsule_env import fingerprint

        profile = json.loads(a.cost_profile.read_text())
        if (
            profile.get("version") != 1
            or not profile.get("baseline_only")
            or profile.get("environment") != fingerprint()
        ):
            raise ValueError("group calibration mismatch")
    for row in rows:
        if selection_report.get(row["commit"], {}).get("import_hazard"):
            continue
        selected = set(sum(row["workers"], []))
        if a.minimal:
            from blast.patches import parse_patch

            edits = parse_patch(
                (a.data / "commits" / f"{row['commit']}.patch").read_text()
            )
            if any(
                not e.old_path.startswith("sqlglot/") or not e.old_path.endswith(".py")
                for e in edits
            ):
                continue
        # Heavy lifecycle, subprocess and resource tests retain their existing verifier path.
        candidates = {
            i
            for i in selected
            if ds[i] <= 2000
            and not (a.cheap_modules and tests[i]["file"] == "tests/test_optimizer.py")
            and not tests[i]["file"].startswith(
                ("tests/test_executor", "tests/test_sqlglotc")
            )
            and "memory" not in tests[i]["id"]
            and ("lazy_load" not in tests[i]["id"] or profile is not None)
        }
        if profile:
            candidates &= {ids[node] for node in profile["passed"] if node in ids}
        original = schedule_cost(row["workers"], ds) / 1000
        floor = schedule_cost(optimize_schedule(selected - candidates, ds), ds) / 1000
        gain = original - floor
        estimate = 0.8 + a.seconds_factor * sum(ds[i] for i in candidates) / 1000
        if profile:
            # Measured CPU rather than the organizer's historical durations.
            # Whole-suite import/fixture overhead is a conservative group estimate.
            estimate = max(0.25, profile["overhead_cpu"]) + 1.5 * sum(
                max(0.001, profile["costs"][tests[i]["id"]]) for i in candidates
            )
        if (
            gain <= estimate
            or cpu() + estimate > a.budget
            or time.monotonic() - wall >= a.wall_budget
        ):
            continue
        tick = cpu()
        try:
            passed = run_group(
                a.source,
                (a.data / "commits" / f"{row['commit']}.patch").read_text(),
                [tests[i]["id"] for i in sorted(candidates)],
                min(
                    8,
                    max(0.1, a.budget - cpu()),
                    max(0.01, a.wall_budget - (time.monotonic() - wall)),
                ),
                minimal=a.minimal,
                warm=a.warm_fork,
            )
        except (OSError, ValueError):
            passed = set()
        removed = {ids[n] for n in passed}
        selected -= removed
        row["workers"] = optimize_schedule(selected, ds)
        report.append(
            dict(
                commit=row["commit"],
                attempted=len(candidates),
                removed=len(removed),
                cpu=cpu() - tick,
                saving=original - schedule_cost(row["workers"], ds) / 1000,
            )
        )
    a.output.write_text("".join(json.dumps(r) + "\n" for r in rows))
    a.report.write_text(json.dumps(dict(cpu=cpu(), actions=report), indent=2))
    print(json.dumps(dict(stage="group_verifier", cpu=cpu(), actions=report)))


if __name__ == "__main__":
    main()
