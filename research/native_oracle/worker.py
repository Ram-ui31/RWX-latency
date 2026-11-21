"""Run the original TPC-DS test with only identical native SELECT work memoized.

Original CSV setup, SQLGlot computation, spawned workers, serialization,
DataFrame assertions and class cleanup all execute. Any invalid cache key or
incomplete reference-call inventory is unresolved, never a passing certificate.
"""

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import pickle
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.native_oracle.common import environment, sha, volatile
from research.group_verifier.minimal import Outcomes


def main():
    parser = argparse.ArgumentParser()
    for key in ("source", "cache", "result"):
        parser.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    manifest = json.loads(Path(str(args.cache) + ".json").read_text())
    if (
        manifest.get("version") != 1
        or not manifest.get("baseline_only")
        or manifest["environment"] != environment()
        or sha(args.cache) != manifest["sha256"]
        or sha(source / "tests/test_executor.py") != manifest["test_source"]
    ):
        raise ValueError("native cache identity mismatch")
    for path, digest in manifest["fixture_hashes"].items():
        if sha(source / path) != digest:
            raise ValueError("native fixture changed")
    sys.path.insert(0, str(source))
    # Only an image-built baseline payload whose hash matched above is trusted.
    payload = pickle.loads(gzip.decompress(args.cache.read_bytes()))
    from tests import test_executor as module

    calls = Counter()
    unknown = []
    hits = 0

    class UnknownReference(Exception):
        pass

    def cached(self, sql, tpch=True):
        nonlocal hits
        calls[sql] += 1
        if tpch or sql not in payload["records"]:
            unknown.append("unknown_query")
            raise UnknownReference()
        if sql in self.cache:
            return self.cache[sql]
        record = payload["records"][sql]
        # Recompute the original transpilation under the mutant. Matching only
        # the input SQL would incorrectly reuse a changed native reference.
        native_sql = module.transpile(sql, write="duckdb")[0]
        if volatile(sql) or volatile(native_sql) or native_sql != record["native_sql"]:
            unknown.append("changed_or_volatile_native_sql")
            raise UnknownReference()
        self.cache[sql] = record["frame"].copy(deep=True)
        hits += 1
        return self.cache[sql]

    module.TestExecutor.cached_execute = cached
    result = Outcomes()
    unittest.TestSuite([module.TestExecutor("test_execute_tpcds")]).run(result)
    status = "observed_fail"
    if unknown or result.lifecycle_error:
        status = "unresolved"
    elif list(result.status.values()) == ["pass"] and dict(calls) == payload["calls"]:
        status = "observed_pass"
    args.result.write_text(
        json.dumps(
            dict(
                status=status,
                reference_hits=hits,
                reference_calls=sum(calls.values()),
                unknown=unknown,
                lifecycle_error=result.lifecycle_error,
            )
        )
    )


if __name__ == "__main__":
    main()
