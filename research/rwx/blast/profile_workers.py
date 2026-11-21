"""Build-time instrumentation for work executed by ProcessPoolExecutor.
It returns execution evidence alongside the ordinary result; no sample labels.
"""
from collections import defaultdict
from concurrent.futures import Future, CancelledError, ProcessPoolExecutor
from pathlib import Path
import os
import sys
from .line_coverage import LineMonitor

_worker_state=None
_hook_installed=False


def _audit(event,args):
    state=_worker_state
    if state is not None and event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
        path=state.relative(os.fsdecode(args[0]))
        if path and not path.startswith('.git/'):
            state.reads.add(path)


class Trace:
    def __init__(self,root):
        self.root=Path(root)
        self.paths={}
        self.types={}
        self.calls=defaultdict(set)
        self.reads=set()
        self.modules=set()
        self.lines=defaultdict(set)
        self.monitor=LineMonitor(self.relative,lambda path,line:self.lines[path].add(line))
    def relative(self,filename):
        if not filename:return None
        if filename not in self.paths:
            try:self.paths[filename]=Path(filename).resolve().relative_to(self.root).as_posix()
            except (ValueError,OSError):self.paths[filename]=None
        return self.paths[filename]
    def profile(self,frame,event,arg):
        if event!='call':return
        path=self.relative(frame.f_code.co_filename)
        if path and path.endswith('.py'):
            if path.startswith('sqlglot/'):
                self.monitor.observe_code(frame.f_code,path)
            self.calls[path].add(frame.f_code.co_firstlineno)
            for name in ['self','cls']:
                obj=frame.f_locals.get(name)
                if obj is None:continue
                cls=obj if isinstance(obj,type) else type(obj)
                if cls not in self.types:
                    module=sys.modules.get(getattr(cls,'__module__',''))
                    self.types[cls]=self.relative(getattr(module,'__file__',None))
                if self.types[cls]:self.modules.add(self.types[cls])
    def payload(self):
        return dict(calls={p:sorted(v) for p,v in self.calls.items()},reads=sorted(self.reads),modules=sorted(self.modules),
                    lines={p:sorted(v) for p,v in self.lines.items()},line_complete=self.monitor.enabled)


def profiled_job(root,fn,args,kwargs):
    global _worker_state,_hook_installed
    if not _hook_installed:
        sys.addaudithook(_audit);_hook_installed=True
    trace=Trace(root)
    _worker_state=trace
    previous=sys.getprofile()
    sys.setprofile(trace.profile)
    result=error=None
    try:
        result=fn(*args,**kwargs)
    except BaseException as exc:
        error=exc
    finally:
        sys.setprofile(previous)
        evidence=trace.payload()
        trace.monitor.close()
        _worker_state=None
    return result,error,evidence


def install_pool_profiling(collector,root):
    """Temporarily bridge result futures so callers receive exactly their results."""
    original=ProcessPoolExecutor.submit
    def submit(executor,fn,/,*args,**kwargs):
        context=collector.active
        if context is None:return original(executor,fn,*args,**kwargs)
        shared=bool(getattr(collector,'shared_depth',0))
        wrapped=original(executor,profiled_job,str(root),fn,args,kwargs)
        exposed=Future()
        def complete(future):
            try:
                result,error,evidence=future.result()
                for path,lines in evidence['calls'].items():
                    for line in lines:
                        collector.calls[path][line].add(context)
                        if shared and hasattr(collector,'shared_calls'):
                            collector.shared_calls[path][line].add(context.rsplit('::',1)[0])
                            collector.shared_function_lines[path].add(line)
                for path in evidence['reads']:
                    collector.reads[path].add(context)
                    if hasattr(collector,'fixture_readers') and path.startswith('tests/fixtures/') and path.endswith('.sql'):
                        # Child jobs currently report raw reads, without a
                        # validated reader stack. Never certify those away.
                        collector.fixture_readers[path]['raw'].add(context)
                for path in evidence['modules']:collector.module_users[path].add(context)
                if hasattr(collector,'lines'):
                    for path,lines in evidence['lines'].items():
                        for line in lines:collector.lines[path][line].add(context)
                    if not evidence['line_complete']:
                        collector.line_incomplete.add(context)
                if shared and hasattr(collector,'shared_reads'):
                    for path in evidence['reads']:
                        collector.shared_reads[path].add(context.rsplit('::',1)[0])
                    for path in evidence['modules']:
                        collector.shared_modules[path].add(context.rsplit('::',1)[0])
                if error is not None:exposed.set_exception(error)
                else:exposed.set_result(result)
            except CancelledError:exposed.cancel()
            except BaseException as exc:exposed.set_exception(exc)
        wrapped.add_done_callback(complete)
        return exposed
    ProcessPoolExecutor.submit=submit
    def restore():ProcessPoolExecutor.submit=original
    return restore
