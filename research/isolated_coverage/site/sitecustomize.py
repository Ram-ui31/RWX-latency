# Trace sqlglot/tests lines in spawned/child interpreters when ISOCOV_DIR is set.
import os
_d = os.environ.get('ISOCOV_DIR')
if _d:
    import sys, atexit
    _root = os.environ['ISOCOV_ROOT']
    _lines, _calls = set(), set()
    _mon = sys.monitoring
    _TOOL = 3
    _mon.use_tool_id(_TOOL, 'isocov')
    def _line(code, line):
        f = code.co_filename
        if f.startswith(_root):
            _lines.add((f, line))
        return _mon.DISABLE
    def _start(code, off):
        f = code.co_filename
        if f.startswith(_root):
            _calls.add((f, code.co_firstlineno))
        return _mon.DISABLE
    _mon.register_callback(_TOOL, _mon.events.LINE, _line)
    _mon.register_callback(_TOOL, _mon.events.PY_START, _start)
    _mon.set_events(_TOOL, _mon.events.LINE | _mon.events.PY_START)
    def _dump():
        try:
            import json
            p = os.path.join(_d, 'child-%d.json' % os.getpid())
            with open(p, 'w') as fh:
                json.dump({'lines': sorted(_lines), 'calls': sorted(_calls)}, fh)
        except Exception:
            pass
    atexit.register(_dump)
    try:
        from multiprocessing import util as _u
        _u.Finalize(None, _dump, exitpriority=-100)
    except Exception:
        pass
