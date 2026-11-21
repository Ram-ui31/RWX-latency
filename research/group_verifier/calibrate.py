"""Calibrate unmodified original unittest CPU costs in the build environment."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from blast.catalog import load_catalog
from engine.runner import PatchedTree
from engine.source_origin import verify
from research.observations.capsule_env import fingerprint


def supported(test, duration):
    return (
        duration <= 2000
        and test["file"] != "tests/test_optimizer.py"
        and not test["file"].startswith(("tests/test_executor", "tests/test_sqlglotc"))
        and "memory" not in test["id"]
        and "lazy_load" not in test["id"]
    )


def main():
    parser = argparse.ArgumentParser()
    for key in ("source", "catalog", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args()
    verify(args.source)
    tests, _, durations = load_catalog(args.catalog)
    nodes = [t["id"] for t in tests if supported(t, durations[t["number"]])]
    with PatchedTree(args.source, "") as tree:
        inventory = tree.path.parent / "nodes.json"
        result = tree.path.parent / "costs.json"
        inventory.write_text(json.dumps(nodes))
        env = dict(
            os.environ,
            SKIP_INTEGRATION="0",
            PYTHONDONTWRITEBYTECODE="1",
            PYTHON_CPU_COUNT="2",
            PYTHONPATH=str(tree.path),
        )
        subprocess.run(
            [
                sys.executable,
                "-B",
                str(Path(__file__).with_name("minimal.py")),
                "--source",
                str(tree.path),
                "--nodes",
                str(inventory),
                "--result",
                str(result),
            ],
            cwd=tree.path,
            env=env,
            check=True,
            timeout=100,
        )
        data = json.loads(result.read_text())
    if data["lifecycle_error"]:
        raise ValueError("baseline group lifecycle error")
    data.update(version=1, baseline_only=True, environment=fingerprint())
    args.output.write_text(json.dumps(data, sort_keys=True))
    print(
        "group calibration",
        len(data["passed"]),
        "tests",
        data["total_cpu"],
        "CPU",
        flush=True,
    )


if __name__ == "__main__":
    main()
