#!/usr/bin/env python3
"""Research feasibility experiment: run ORIGINAL whole literal-helper tests.

Not a selector, capsule compiler, safety proof, or canonical pytest run.
The driver never reads answers. Compare its observations offline afterwards.
Every patch gets a fresh interpreter and original unittest TestCase methods.
Only syntactically simple dialect methods enter this deliberately narrow pilot.
"""
import argparse
import ast
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'rwx'))
from blast.catalog import load_catalog
from blast.patches import apply_change, parse_patch
from blast.selection import SourceIndex


def eligible_method(node):
    if node.decorator_list or not node.body:
        return False
    count = 0
    for stmt in node.body:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
            continue
        if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
            return False
        call = stmt.value
        if not (isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)
                and call.func.value.id == 'self' and call.func.attr in {'validate_identity', 'validate_all'}):
            return False
        try:
            for arg in call.args:
                ast.literal_eval(arg)
            for kw in call.keywords:
                if kw.arg is None:
                    return False
                ast.literal_eval(kw.value)
        except (ValueError, TypeError, SyntaxError):
            return False
        count += 1
    return count > 0


def inventory(payload, tests):
    trees = {p: ast.parse(i['source']) for p, i in payload['files'].items()
             if p.startswith('tests/dialects/')}
    methods = {}
    for path, tree in trees.items():
        for cls in tree.body:
            if not isinstance(cls, ast.ClassDef):
                continue
            for node in cls.body:
                if isinstance(node, ast.FunctionDef) and eligible_method(node):
                    methods[f'{path}::{cls.name}::{node.name}'] = node
    return [t for t in tests if t['id'] in methods]


def child(job_path):
    # This branch imports the real pinned test code, never the research answers.
    job = json.loads(Path(job_path).read_text())
    os.chdir(job['tree'])
    sys.path.insert(0, job['tree'])
    import unittest
    class Result(unittest.TestResult):
        def __init__(self):
            super().__init__()
            self.failed_ids = set()
            self.error_ids = set()
            self.skipped_ids = set()
        def addFailure(self, test, err):
            self.failed_ids.add(test.id())
            super().addFailure(test, err)
        def addError(self, test, err):
            self.error_ids.add(test.id())
            super().addError(test, err)
        def addSkip(self, test, reason):
            self.skipped_ids.add(test.id())
            super().addSkip(test, reason)
        def addSubTest(self, test, subtest, err):
            if err is not None:
                (self.failed_ids if issubclass(err[0], test.failureException) else self.error_ids).add(test.id())
            super().addSubTest(test, subtest, err)
    result = Result()
    reverse = {}
    for t in job['tests']:
        dotted = t['file'][:-3].replace('/', '.') + '.' + '.'.join(t['id'].split('::')[1:])
        reverse[dotted] = t['number']
        try:
            suite = unittest.defaultTestLoader.loadTestsFromName(dotted)
            # A module import failure from the loader is an unknown observation.
            if unittest.defaultTestLoader.errors:
                result.error_ids.add(dotted)
                unittest.defaultTestLoader.errors.clear()
                continue
            suite.run(result)
        except Exception:
            result.error_ids.add(dotted)
    failed = sorted(reverse[i] for i in result.failed_ids if i in reverse)
    unknown = sorted(reverse[i] for i in result.error_ids | result.skipped_ids if i in reverse)
    # Fixture/lifecycle errors can name ErrorHolder rather than a test. Fail closed.
    global_errors = sorted(i for i in result.error_ids if i not in reverse)
    if global_errors:
        unknown = sorted(t['number'] for t in job['tests'])
    Path(job['result']).write_text(json.dumps(dict(
        requested=len(job['tests']), tests_run=result.testsRun,
        observed_failures=failed, unknown=unknown, lifecycle_errors=global_errors,
    )))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--python', default=sys.executable)
    ap.add_argument('--output', type=Path, default=ROOT / 'rwx_next/reports/replay_smoke.json')
    ap.add_argument('--child', type=Path)
    args = ap.parse_args()
    if args.child:
        child(args.child)
        return
    start = time.monotonic()
    cpu_start = time.process_time()
    with gzip.open(ROOT / 'rwx/maps/impact-index-v5.json.gz', 'rt') as f:
        payload = json.load(f)
    tests, ids, _ = load_catalog(ROOT / 'rwx/sample/sample/tests.json')
    ix = SourceIndex(ROOT / 'rwx/maps/impact-index-v5.json.gz', ids)
    eligible = inventory(payload, tests)
    evidence = dict(
        source_pin=payload['source_commit'], status='noncanonical_research_only',
        purpose='Feasibility of executing original assertions; not safe test omission.',
        answers_read=False, runner='stdlib unittest; original methods and Validator helpers',
        canonical_pytest_equivalence_validated=False,
        eligible_tests=len(eligible), eligible_numbers=[t['number'] for t in eligible],
        uncovered_expensive_tests=[1106, 1107, 1123, 1224, 1490],
        baseline={}, patches={},
    )
    with tempfile.TemporaryDirectory(prefix='rwx-replay-') as folder:
        base = Path(folder)
        tree = base / 'source'
        tree.mkdir()
        for path, info in payload['files'].items():
            content = info['source'].encode()
            if hashlib.sha256(content).hexdigest() != info['sha256']:
                raise ValueError('Source hash mismatch: ' + path)
            dest = tree / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
        for path, info in payload.get('fixtures', {}).items():
            dest = tree / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(info['source'])

        def run(selected):
            result_path = base / 'result.json'
            result_path.unlink(missing_ok=True)
            job = base / 'job.json'
            job.write_text(json.dumps(dict(tree=str(tree), tests=selected, result=str(result_path))))
            before = resource.getrusage(resource.RUSAGE_CHILDREN)
            tick = time.monotonic()
            proc = subprocess.run([args.python, '-B', str(Path(__file__).resolve()), '--child', str(job)],
                                  capture_output=True, text=True, timeout=45,
                                  env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            after = resource.getrusage(resource.RUSAGE_CHILDREN)
            result = json.loads(result_path.read_text()) if result_path.exists() else dict(
                requested=len(selected), observed_failures=[], unknown=[t['number'] for t in selected])
            result.update(exit_code=proc.returncode,
                          child_cpu_seconds=(after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime),
                          wall_seconds=time.monotonic() - tick,
                          stderr_tail=proc.stderr[-400:] if proc.returncode else '')
            return result

        evidence['baseline'] = run(eligible)
        for patch in sorted((ROOT / 'rwx/sample/sample/commits').glob('*.patch')):
            changes = parse_patch(patch.read_text())
            touched = []
            try:
                for change in changes:
                    path = change.old_path
                    info = payload['files'].get(path) or payload.get('fixtures', {}).get(path)
                    if not info or path != change.new_path:
                        raise ValueError('Unrepresented or structural edit')
                    (tree / path).write_text(apply_change(info['source'], change))
                    touched.append((path, info['source']))
                candidates, _ = ix.select(patch.read_text(), mode='hybrid')
                selection = [t for t in eligible if t['number'] in candidates]
                evidence['patches'][patch.stem] = run(selection) if selection else dict(
                    requested=0, tests_run=0, observed_failures=[], unknown=[], child_cpu_seconds=0)
            except Exception as ex:
                evidence['patches'][patch.stem] = dict(status='unsupported', reason=type(ex).__name__)
            finally:
                for path, source in touched:
                    (tree / path).write_text(source)
    evidence['total_wall_seconds'] = time.monotonic() - start
    evidence['driver_cpu_seconds'] = time.process_time() - cpu_start
    evidence['patch_child_cpu_seconds'] = sum(p.get('child_cpu_seconds', 0) for p in evidence['patches'].values())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps({k: v for k, v in evidence.items() if k not in ('patches', 'eligible_numbers')}, indent=2))


if __name__ == '__main__':
    main()
