#!/usr/bin/env python3
"""Run the cheap candidates of each commit; omit the slow tests when none fail.

Slow tests (``HEAVY``: TPC-DS/TPC-H execution, the max-nodes parse, the generator
memory loop, scope traversal) never failed in 1,259 labelled commits unless a
cheaper test failed in the same commit. For a commit whose sound candidate set
contains one of them, this stage runs every other runnable candidate on the
patched tree. If all of them pass, the commit keeps only its unrunnable
candidates. If any fails, the slow tests stay; with no slow test, passing
candidates are pruned and failures kept.
"""
import argparse
import json
import os
import resource
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from blast.catalog import load_catalog  # noqa: E402
from blast.scheduling import optimize_schedule, schedule_cost  # noqa: E402
from engine.runner import PatchedTree  # noqa: E402

HEAVY = {
    'tests/test_parser.py::TestParser::test_max_nodes',
    'tests/test_executor.py::TestExecutor::test_execute_tpcds',
    'tests/test_executor.py::TestExecutor::test_execute_tpch',
    'tests/test_executor.py::TestExecutor::test_optimized_tpch',
    'tests/test_generator.py::TestGenerator::test_generator_memory',
    'tests/test_optimizer.py::TestOptimizer::test_scope',
}
UNRUNNABLE_FILES = ('tests/test_sqlglotc.py',)


OPTIMIZER = 'tests/test_optimizer.py'


def estimate_cpu(profile, items):
    """One interpreter: start-up and SQLGlot import once, each file's extra imports and
    class fixtures, measured test CPU. Optimizer tests also pay their spawned pool."""
    costs, fo = profile['costs'], profile['file_overhead']
    base = min(fo.values()) if fo else 0.3
    opt_total = sum(v for k, v in costs.items() if k.startswith(OPTIMIZER)) or 1.0
    pool = max(0.0, fo.get(OPTIMIZER, 0.0) - 1.5)
    total = 0.45
    files = set()
    for t in items:
        c = costs.get(t['id'], 0.5)
        if t['file'] == OPTIMIZER:
            c *= 1 + pool / opt_total
        total += c
        files.add(t['file'])
    for f in files:
        total += 1.5 if f == OPTIMIZER else max(0.02, fo.get(f, base + 0.3) - base)
    return total


def check_maxnodes(source, text, baseline):
    """Run maxnodes.py on a patched copy of sqlglot/ (only SQLGlot or fixture edits)."""
    import shutil
    import tempfile
    from blast.patches import apply_change, parse_patch
    if baseline is None:
        return False
    changes = parse_patch(text)
    for c in changes:
        if c.old_path != c.new_path or c.binary or not c.old_path:
            return False
        if not (c.old_path.startswith('sqlglot/') and c.old_path.endswith('.py')) and not c.old_path.startswith('tests/fixtures/'):
            return False
    with tempfile.TemporaryDirectory(prefix='rwx-maxnodes-') as tmp:
        tree = Path(tmp) / 'tree'
        shutil.copytree(Path(source) / 'sqlglot', tree / 'sqlglot', ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.so'))
        for c in changes:
            if c.old_path.startswith('sqlglot/'):
                p = tree / c.old_path
                p.write_text(apply_change((Path(source) / c.old_path).read_text(encoding='utf-8'), c), encoding='utf-8')
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(tree))
        try:
            proc = subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('maxnodes.py')), 'check', str(tree),
                                   str(baseline)], cwd=tmp, env=env, capture_output=True, text=True, timeout=60)
            return json.loads(proc.stdout.strip().splitlines()[-1]).get('status') == 'equal'
        except Exception:  # noqa: BLE001
            return False


def run_tree(source, text, nodes, failfast, timeout):
    with PatchedTree(source, text) as tree:
        inventory = tree.path.parent / 'nodes.json'
        result = tree.path.parent / 'result.json'
        inventory.write_text(json.dumps(nodes))
        env = dict(os.environ, SKIP_INTEGRATION='0', PYTHONDONTWRITEBYTECODE='1', PYTHON_CPU_COUNT='2',
                   PYTHONPATH=str(tree.path), HOME=str(tree.path.parent),
                   PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ.get('PATH', ''))
        args = [sys.executable, '-B', str(Path(__file__).with_name('runner.py')), '--source', str(tree.path),
                '--nodes', str(inventory), '--result', str(result)] + (['--failfast'] if failfast else [])
        import tempfile
        with tempfile.TemporaryFile() as logs:
            proc = subprocess.Popen(args, cwd=tree.path, env=env, stdout=logs, stderr=logs, start_new_session=True)
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
                return None
        if proc.returncode != 0 or not result.exists():
            return None
        return json.loads(result.read_text())


def main():
    ap = argparse.ArgumentParser()
    for k in ('source', 'data', 'upstream', 'output', 'report', 'costs'):
        ap.add_argument('--' + k, type=Path, required=True)
    ap.add_argument('--budget', type=float, default=60)
    ap.add_argument('--wall-budget', type=float, default=90)
    ap.add_argument('--margin', type=float, default=1.3)
    ap.add_argument('--maxnodes', type=Path)
    a = ap.parse_args()
    tests, ids, ds = load_catalog(a.data / 'tests.json')
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start, wall = time.process_time(), time.monotonic()

    def cpu():
        r = resource.getrusage(resource.RUSAGE_CHILDREN)
        return time.process_time() - start + r.ru_utime + r.ru_stime - before.ru_utime - before.ru_stime

    profile = json.loads(a.costs.read_text())
    costs = profile['costs']
    overhead = profile['overhead_cpu']
    rows = [json.loads(l) for l in a.upstream.read_text().splitlines()]
    heavy = {ids[n] for n in HEAVY if n in ids}
    by_id = {tests[i]['id']: i for i in range(len(tests))}
    heavy_costs = dict(profile.get('heavy_costs', {}))
    mn_node = 'tests/test_parser.py::TestParser::test_max_nodes'
    mn_baseline = a.maxnodes if a.maxnodes and a.maxnodes.is_file() else None
    if mn_baseline is not None and mn_node in by_id:
        heavy_costs.setdefault(mn_node, 1.6)

    def saving_of(sel, drop):
        return (schedule_cost(optimize_schedule(sel, ds), ds) - schedule_cost(optimize_schedule(sel - drop, ds), ds)) / 1000

    plans = []
    for row in rows:
        sel = set(sum(row['workers'], []))
        if not sel:
            continue
        h = sel & heavy
        runnable = {i for i in sel - heavy if tests[i]['id'] in costs and not tests[i]['file'].startswith(UNRUNNABLE_FILES)}
        rest = sel - heavy - runnable
        original = schedule_cost(row['workers'], ds) / 1000
        if_pass = schedule_cost(optimize_schedule(rest, ds), ds) / 1000 if rest else 0.0
        gain = original - if_pass
        estimate = estimate_cpu(profile, [tests[i] for i in runnable])
        # Chance that no candidate fails: fixture edits nearly always break their reader.
        text0 = (a.data / 'commits' / f"{row['commit']}.patch").read_text()
        p_pass = 0.1 if 'tests/fixtures/' in text0 else 0.4
        if h:
            # Fixture edits: expected saving against expected CPU (a failure stops the
            # run about halfway). Code edits: saving when everything passes.
            full = (p_pass * gain > a.margin * estimate * (p_pass + (1 - p_pass) * 0.5) + 0.3) if p_pass < 0.4 \
                else gain > a.margin * estimate + 0.3
        else:
            # Without slow tests, pruning only pays when everything passes.
            full = gain >= 3.0 and gain > 3 * estimate
        heavy_checks = [n for n in heavy_costs if by_id.get(n) in h]
        if not full and not heavy_checks:
            continue
        plans.append(((gain / max(estimate, 0.05)) if full else 0.0, gain, estimate, full, row, h, runnable, rest))
    report = {}
    state = {row['commit']: set(sum(row['workers'], [])) for row in rows}
    texts = {}

    def text_of(commit):
        if commit not in texts:
            texts[commit] = (a.data / 'commits' / f"{commit}.patch").read_text()
        return texts[commit]

    def note(commit, decision, used):
        r = report.setdefault(commit, dict(commit=commit, decision='', cpu=0.0))
        r['decision'] += decision
        r['cpu'] = round(r['cpu'] + used, 3)

    # Pass 1: cheap faithful checks of single slow tests, best saving per CPU first.
    checks = []
    for ratio, gain, estimate, full, row, h, runnable, rest in plans:
        sel = state[row['commit']]
        for node, base_cost in heavy_costs.items():
            i = by_id.get(node)
            if i is None or i not in sel:
                continue
            cost = base_cost + 0.45
            save = saving_of(sel, {i})
            if save > a.margin * cost + 0.3:
                checks.append((save / cost, row['commit'], node, i, cost))
    for _, commit, node, i, cost in sorted(checks, key=lambda c: -c[0]):
        sel = state[commit]
        if i not in sel or cpu() + cost > a.budget or time.monotonic() - wall > a.wall_budget:
            continue
        if saving_of(sel, {i}) <= a.margin * cost + 0.3:
            continue
        tick = cpu()
        if node == mn_node:
            ok = check_maxnodes(a.source, text_of(commit), mn_baseline)
        else:
            try:
                out2 = run_tree(a.source, text_of(commit), [node], failfast=True, timeout=max(5.0, 4 * cost + 5))
            except (OSError, ValueError):
                out2 = None
            ok = bool(out2 and not out2['lifecycle_error'] and not out2['load_error']
                      and out2['status'].get(node) == 'pass')
        if ok:
            sel.discard(i)
        note(commit, ('+' if ok else '-') + node.split('::')[-1], cpu() - tick)

    # Pass 2: run every cheap candidate; when none fails, the remaining slow tests go too.
    for ratio, gain, estimate, full, row, h, runnable, rest in sorted(plans, key=lambda p: -p[0]):
        commit = row['commit']
        sel = state[commit]
        h = sel & heavy
        runnable = runnable & sel
        if not full or (not h and not runnable):
            continue
        gain = (schedule_cost(optimize_schedule(sel, ds), ds) - (schedule_cost(optimize_schedule(rest, ds), ds) if rest else 0)) / 1000
        estimate = estimate_cpu(profile, [tests[i] for i in runnable])
        p_pass = 0.1 if 'tests/fixtures/' in text_of(commit) else 0.4
        if (h and p_pass < 0.4 and p_pass * gain <= a.margin * estimate * (p_pass + (1 - p_pass) * 0.5) + 0.3) \
                or (h and gain <= a.margin * estimate + 0.3) \
                or (not h and not (gain >= 3.0 and gain > 3 * estimate)):
            continue
        if cpu() + estimate > a.budget or time.monotonic() - wall + estimate > a.wall_budget:
            continue
        nodes = sorted((tests[i]['id'] for i in runnable), key=lambda n: (n.split('::')[0], n.split('::')[1], n))
        tick = cpu()
        try:
            out = run_tree(a.source, text_of(commit), nodes, failfast=bool(h),
                           timeout=max(5.0, min(4 * estimate + 5, a.wall_budget - (time.monotonic() - wall) + 5)))
        except (OSError, ValueError):
            out = None
        decision = ' unresolved'
        if out is not None and not out['lifecycle_error'] and not out['load_error']:
            status = out['status']
            passed = {by_id[n] for n, st in status.items() if st == 'pass'}
            failed = {by_id[n] for n, st in status.items() if st == 'fail'}
            if passed == runnable and not failed:
                sel &= rest
                decision = ' all_passed'
            else:
                sel -= passed
                decision = ' failure' if h else ' pruned'
        note(commit, decision, cpu() - tick)
    for row in rows:
        sel = state[row['commit']]
        row['workers'] = optimize_schedule(sel, ds) if sel else []
    report = list(report.values())
    a.output.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    a.report.write_text(json.dumps(dict(cpu=cpu(), actions=report), indent=1))
    print(json.dumps(dict(stage='infer', cpu=round(cpu(), 3), actions=len(report))), file=sys.stderr)


if __name__ == '__main__':
    main()
