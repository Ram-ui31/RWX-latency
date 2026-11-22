#!/usr/bin/env python3
"""Measure baseline CPU of every runnable non-slow test, per file, in the build environment."""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from blast.catalog import load_catalog  # noqa: E402
from engine.source_origin import verify  # noqa: E402
from run import HEAVY, UNRUNNABLE_FILES, run_tree  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    for k in ('source', 'catalog', 'output'):
        ap.add_argument('--' + k, type=Path, required=True)
    a = ap.parse_args()
    verify(a.source)
    tests, _, _ = load_catalog(a.catalog)
    by_file = defaultdict(list)
    for t in tests:
        if t['id'] in HEAVY or t['file'].startswith(UNRUNNABLE_FILES):
            continue
        by_file[t['file']].append(t['id'])
    empty = run_tree(a.source, '', [], failfast=False, timeout=120)
    base = empty['total_cpu'] if empty else 0.3
    costs, file_overhead, failed = {}, {}, []
    for f, nodes in sorted(by_file.items()):
        out = run_tree(a.source, '', nodes, failfast=False, timeout=600)
        if out is None or out['lifecycle_error'] or out['load_error']:
            failed.extend(nodes)
            continue
        for n in nodes:
            if out['status'].get(n) == 'pass':
                costs[n] = round(max(0.001, out['costs'][n]), 4)
            else:
                failed.append(n)
        file_overhead[f] = round(max(0.0, out['total_cpu'] - base - sum(out['costs'].values())), 4)
    heavy_costs = {}
    for node in ('tests/test_generator.py::TestGenerator::test_generator_memory',
                 'tests/test_optimizer.py::TestOptimizer::test_scope'):
        out = run_tree(a.source, '', [node], failfast=True, timeout=300)
        if out and out['status'].get(node) == 'pass':
            heavy_costs[node] = round(out['total_cpu'], 4)
    Path(a.output).write_text(json.dumps(dict(version=1, overhead_cpu=round(base, 4), file_overhead=file_overhead,
                                              costs=costs, heavy_costs=heavy_costs, not_passing=failed)))
    print('infer calibration', len(costs), 'tests', round(sum(costs.values()), 2), 'CPU; base', round(base, 3),
          'file overhead', round(sum(file_overhead.values()), 2), 'not passing', len(failed), file=sys.stderr)


if __name__ == '__main__':
    main()
