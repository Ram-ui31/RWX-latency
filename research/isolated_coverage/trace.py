#!/usr/bin/env python3
"""Isolated per-test line/function coverage of the pinned SQLGlot tests.

Process tree: base (imports sqlglot; its lines belong to every test) ->
module child (imports one test module; its lines belong to every test of that
module) -> test grandchild (setUpClass + one test + class cleanup). Spawned
interpreters are traced through sitecustomize and attributed to the test.

usage: trace.py ROOT TESTS_JSON OUT_DIR SHARD NSHARDS
"""
import json, os, sys, time, unittest, importlib, signal
from collections import defaultdict

def main():
    global LINES, CALLS, prefix, root, out
    root, tests_json, out, shard, nshards = sys.argv[1:6]
    shard, nshards = int(shard), int(nshards)
    root = os.path.abspath(root)
    os.chdir(root)
    sys.path.insert(0, root)
    os.environ['SKIP_INTEGRATION'] = '0'
    SITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'site')
    os.makedirs(out, exist_ok=True)
    prefix = root + os.sep

    mon = sys.monitoring
    TOOL = 2
    LINES, CALLS = set(), set()
    mon.use_tool_id(TOOL, 'isocov-main')


    def _line(code, line):
        if code.co_filename.startswith(prefix):
            LINES.add((code.co_filename[len(prefix):], line))
        return mon.DISABLE


    def _start(code, off):
        if code.co_filename.startswith(prefix):
            CALLS.add((code.co_filename[len(prefix):], code.co_firstlineno))
        return mon.DISABLE


    mon.register_callback(TOOL, mon.events.LINE, _line)
    mon.register_callback(TOOL, mon.events.PY_START, _start)
    mon.set_events(TOOL, mon.events.LINE | mon.events.PY_START)

    import sqlglot  # noqa: E402  (base import, traced)


    def dump(path, **extra):
        with open(path, 'w') as fh:
            json.dump(dict(lines=sorted(LINES), calls=sorted(CALLS), **extra), fh)


    if shard == 0:
        dump(os.path.join(out, 'base.json'))

    tests = json.load(open(tests_json))['tests']
    by_module = defaultdict(list)
    for t in tests:
        f, cls, meth = t['id'].split('::')
        by_module[f].append((t['number'], cls, meth))
    modules = sorted(by_module)
    mine = [m for i, m in enumerate(modules) if i % nshards == shard]


    def strip_root(p):
        return p[len(prefix):] if p.startswith(prefix) else None


    def run_one(number, mod, cls_name, meth):
        LINES.clear(); CALLS.clear()
        cdir = os.path.join(out, 'children', str(number))
        os.makedirs(cdir, exist_ok=True)
        os.environ['ISOCOV_DIR'] = cdir
        os.environ['ISOCOV_ROOT'] = prefix
        os.environ['PYTHONPATH'] = SITE + os.pathsep + root + os.pathsep + os.environ.get('PYTHONPATH', '')
        cls = getattr(mod, cls_name)
        result = unittest.TestResult()
        status = 'passed'
        t0 = time.process_time()
        try:
            if getattr(cls, '__unittest_skip__', False):
                status = 'skipped'
            else:
                try:
                    cls.setUpClass()
                except Exception as e:
                    status = 'class_setup_error:' + repr(e)[:200]
                    cls.doClassCleanups()
                if status == 'passed':
                    case = cls(meth)
                    case.run(result)
                    try:
                        cls.tearDownClass()
                    finally:
                        cls.doClassCleanups()
                    if result.errors or result.failures:
                        status = 'failed'
                    elif result.skipped and not result.testsRun - len(result.skipped):
                        status = 'skipped'
        except BaseException as e:  # noqa
            status = 'crash:' + repr(e)[:200]
        cpu = time.process_time() - t0
        dump(os.path.join(out, f'test-{number}.json'), status=status, cpu=cpu,
             errors=[str(x[1])[-500:] for x in result.errors + result.failures][:3])


    for modfile in mine:
        pid = os.fork()
        if pid == 0:
            try:
                LINES.clear(); CALLS.clear()
                modname = modfile[:-3].replace('/', '.')
                mod = importlib.import_module(modname)
                dump(os.path.join(out, 'module-' + modfile.replace('/', '__') + '.json'),
                     tests=[n for n, _, _ in by_module[modfile]])
                for number, cls_name, meth in by_module[modfile]:
                    p2 = os.fork()
                    if p2 == 0:
                        try:
                            signal.alarm(600)
                            run_one(number, mod, cls_name, meth)
                        finally:
                            os._exit(0)
                    _, st = os.waitpid(p2, 0)
                    if not os.path.exists(os.path.join(out, f'test-{number}.json')):
                        with open(os.path.join(out, f'test-{number}.json'), 'w') as fh:
                            json.dump(dict(lines=[], calls=[], status='lost:%d' % st, cpu=0), fh)
            except BaseException as e:  # noqa
                with open(os.path.join(out, 'module-error-' + modfile.replace('/', '__')), 'w') as fh:
                    fh.write(repr(e))
            finally:
                os._exit(0)
        os.waitpid(pid, 0)
    print('shard done', shard, len(mine), file=sys.stderr)


if __name__ == '__main__':
    main()
