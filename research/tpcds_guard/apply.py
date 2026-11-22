"""Runtime use of the TPC differential guard (see guard.py)."""
import json
import os
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from blast.patches import apply_change, parse_patch  # noqa: E402
from engine.astdiff import classify  # noqa: E402

TESTS = {'tpcds': 'tests/test_executor.py::TestExecutor::test_execute_tpcds',
         'tpch': 'tests/test_executor.py::TestExecutor::test_execute_tpch',
         'opt_tpch': 'tests/test_executor.py::TestExecutor::test_optimized_tpch'}


class Guard:
    def __init__(self, baseline):
        self.baseline = Path(baseline)
        data = json.loads(self.baseline.read_text())
        self.names = None
        self.source_root = None
        self.outside = {s: {(f, l) for f, l in v['outside']} for s, v in data['suites'].items()}

    TPCH_SQL = 'tests/fixtures/optimizer/tpc-h/tpc-h.sql'
    TPCDS_SQL = 'tests/fixtures/optimizer/tpc-ds/tpc-ds.sql'

    def analyze(self, source, text):
        """(edited lines, edited value names with own spans, fixture files, sqlglot changed) or None."""
        lines, names, fixtures, code = set(), [], [], False
        for change in parse_patch(text):
            path = change.old_path
            if not (path and path == change.new_path and not change.binary and change.hunks):
                return None
            if path.startswith('tests/fixtures/'):
                if path.endswith('.csv') or path.endswith('.gz') or '/tpc-h/' in path and path != self.TPCH_SQL \
                        or '/tpc-ds/' in path and path != self.TPCDS_SQL:
                    return None
                fixtures.append(path)
                continue
            if not (path.startswith('sqlglot/') and path.endswith('.py')):
                return None
            old = (Path(source) / path).read_text(encoding='utf-8')
            kind, spans, lambdas = classify(old, apply_change(old, change))
            if kind == 'noop':
                continue
            code = True
            if lambdas:
                return None
            if kind == 'body':
                for a, b in spans:
                    lines.update((path, n) for n in range(a, b + 1))
            elif kind == 'value':
                for qual, targets, span in spans:
                    for name in targets:
                        if name.startswith('__'):
                            return None
                        names.append((name, path, span, bool(qual) and name.isupper()))
            else:
                return None
        return lines, names, fixtures, code

    def names_clear(self, suite, names):
        if not names:
            return True
        if self.names is None:
            from engine.names import NameIndex
            self.names = NameIndex(self.source_root)
        outside = self.outside[suite]
        for name, path, span, setting in names:
            for f, a, b in self.names.lines_for(name, class_setting=setting):
                for line in range(a, b + 1):
                    if (f, line) in outside and not (f == path and span[0] <= line <= span[1]):
                        return False
        return True

    def eligible_suites(self, source, text, suites):
        """[(suite list to recompute, fixture checks)] decision for the selected suites."""
        self.source_root = source
        info = self.analyze(source, text)
        if info is None:
            return [], []
        lines, names, fixtures, code = info
        out = []
        for s in suites:
            if not lines.isdisjoint(self.outside[s]) or not self.names_clear(s, names):
                continue
            if s == 'tpcds' and self.TPCDS_SQL in fixtures:
                continue
            if s in ('tpch', 'opt_tpch') and self.TPCH_SQL in fixtures:
                continue
            out.append(s)
        checks = [f for f in fixtures if f in (self.TPCH_SQL, self.TPCDS_SQL)]
        return out, checks

    def check(self, source, text, suites, fixtures=(), timeout=30):
        info = self.analyze(source, text)
        lines = None
        if info:
            lines = set(info[0])
            if info[1]:
                if self.names is None:
                    from engine.names import NameIndex
                    self.names = NameIndex(source)
                for name, path, span, setting in info[1]:
                    lines.update((path, n) for n in range(span[0], span[1] + 1))
                    for f, a, b in self.names.lines_for(name, class_setting=setting):
                        lines.update((f, n) for n in range(a, b + 1))
        """Return ({suite: 'equal'|other}, cpu seconds); fixture failures make every suite unresolved."""
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        status = {}
        with tempfile.TemporaryDirectory(prefix='rwx-guard-') as tmp:
            tree = Path(tmp) / 'tree'
            try:
                shutil.copytree(Path(source) / 'sqlglot', tree / 'sqlglot',
                                ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.so'))
                for change in parse_patch(text):
                    p = tree / change.old_path
                    p.parent.mkdir(parents=True, exist_ok=True)
                    original = Path(source) / change.old_path
                    p.write_text(apply_change(original.read_text(encoding='utf-8'), change), encoding='utf-8')
                edited = Path(tmp) / 'edited.json'
                edited.write_text(json.dumps(sorted(f'{f}:{n}' for f, n in (lines or ()))))
                env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': str(tree),
                       'RWX_PINNED_ROOT': str(Path(source).resolve())}
                if lines is not None:
                    env['RWX_GUARD_EDITED'] = str(edited)
                args = [*suites, *('fixture=' + str(tree / f) for f in fixtures)]
                proc = subprocess.Popen([sys.executable, '-B', str(HERE / 'guard.py'), 'check', str(tree),
                                         str(self.baseline), *args], cwd=tmp, env=env,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                        start_new_session=True)
                try:
                    out, _ = proc.communicate(timeout=timeout)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL); proc.wait(); out = ''
                if proc.returncode == 0 and out.strip():
                    result = json.loads(out.strip().splitlines()[-1])
                    status = {s: result.get(s, 'unresolved') for s in suites}
            except Exception:
                status = {}
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        return status, after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime
