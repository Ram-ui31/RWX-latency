"""Validate committed native baseline maps against the actual build environment."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.source_origin import verify
from research.observations.capsule_env import fingerprint


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    verify(args.source)
    assets = ROOT / "assets"
    records = {
        name: json.loads(gzip.decompress((assets / (name + ".json.gz")).read_bytes()))
        for name in ("observations", "settings", "arguments")
    }
    source = {
        p.relative_to(args.source).as_posix(): sha(p)
        for p in (args.source / "sqlglot").rglob("*.py")
    }
    for record in records.values():
        if record["environment"] != fingerprint() or record["source"] != source:
            raise ValueError(
                "native baseline source or environment mismatch; regenerate maps"
            )
    obs, settings, arguments = (
        records[k] for k in ("observations", "settings", "arguments")
    )
    index_hash = sha(ROOT / "maps/source-index.json.gz")
    if (
        obs["version"] != 2
        or not obs.get("per_task_ownership")
        or len(obs["passed"]) < 1500
        or obs["source_index_sha256"] != index_hash
        or settings["version"] != 9
        or not settings["task_attribution"]
        or settings["validation_order_guard"] != "multiple_missing"
        or not settings["test_code_instrumented"]
        or len(settings["passed"]) != 1620
        or arguments["version"] != 1
        or arguments["unknown_classes"]
        or arguments["index_sha256"] != index_hash
        or arguments["readers_sha256"] != sha(assets / "settings.json.gz")
    ):
        raise ValueError("native baseline artifact binding mismatch")
    print("Validated native baseline source, runtime and artifact bindings")


if __name__ == "__main__":
    main()
