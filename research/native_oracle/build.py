"""Capture native reference frames from unmodified SQLGlot and public fixtures.

This is not a mutation/answer cache. Runtime must recompute the complete
SQLGlot side and match the native SQL, fixture data and environment exactly.
"""

import argparse
from collections import Counter
import gzip
import json
import os
from pathlib import Path
import pickle
import resource
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from engine.source_origin import verify
from research.native_oracle.common import environment, sha, volatile


def main():
    parser = argparse.ArgumentParser()
    for key in ("source", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    verify(source)
    sys.path.insert(0, str(source))
    from tests import test_executor as module

    case = module.TestExecutor("test_execute_tpcds")
    records = {}
    calls = Counter()
    unsafe = []
    actual_sql = {}
    original_transpile = module.transpile

    def capture_sql(sql, *a, **kw):
        value = original_transpile(sql, *a, **kw)
        if kw.get("write") == "duckdb":
            actual_sql[sql] = value[0]
        return value

    module.transpile = capture_sql
    case.setUpClass()
    try:
        for meta, sql, _ in case.tpcds_sqls:
            if not meta.get("execute"):
                continue
            frame = case.cached_execute(sql, tpch=False)
            native_sql = actual_sql[sql]
            if volatile(sql) or volatile(native_sql):
                unsafe.append(sql)
            records[sql] = dict(native_sql=native_sql, frame=frame.copy(deep=True))
            calls[sql] += 1
    finally:
        case.tearDownClass()
        module.transpile = original_transpile
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(
        gzip.compress(
            pickle.dumps(dict(records=records, calls=dict(calls)), protocol=5), mtime=0
        )
    )
    manifest = dict(
        version=1,
        baseline_only=True,
        environment=environment(),
        sha256=sha(args.output),
        unsafe_queries=unsafe,
        reference_calls=sum(calls.values()),
        fixture_hashes={
            p.relative_to(source).as_posix(): sha(p)
            for p in (source / "tests/fixtures").rglob("*")
            if p.is_file()
        },
        test_source=sha(source / "tests/test_executor.py"),
    )
    manifest_path = Path(str(args.output) + ".json")
    manifest_path.write_text(json.dumps(manifest, sort_keys=True))
    with tempfile.TemporaryDirectory(prefix="rwx-native-calibrate-") as directory:
        result = Path(directory) / "result.json"
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        tick = time.monotonic()
        proc = subprocess.run(
            [
                sys.executable,
                "-B",
                str(Path(__file__).with_name("worker.py")),
                "--source",
                str(source),
                "--cache",
                str(args.output.resolve()),
                "--result",
                str(result),
            ],
            cwd=source,
            env=dict(
                os.environ,
                PYTHON_CPU_COUNT="2",
                SKIP_INTEGRATION="0",
                PYTHONDONTWRITEBYTECODE="1",
                PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"],
            ),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
        )
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        used = after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime
        evidence = (
            json.loads(result.read_text())
            if result.exists()
            else dict(status="unresolved")
        )
        manifest.update(
            baseline_status=evidence["status"],
            baseline_cpu_seconds=used,
            baseline_wall_seconds=time.monotonic() - tick,
            baseline_reference_hits=evidence.get("reference_hits", 0),
        )
    manifest_path.write_text(json.dumps(manifest, sort_keys=True))
    print(
        json.dumps(
            dict(
                reference_calls=sum(calls.values()),
                unsafe=len(unsafe),
                baseline=evidence,
                cpu=used,
            )
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
