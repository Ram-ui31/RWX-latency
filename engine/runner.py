"""Original pytest validation in a fresh patched source tree, with CPU charging."""
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import platform
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time

PLUGIN = '''import json,os
reports=[]
def pytest_runtest_logreport(report):
    reports.append(dict(nodeid=report.nodeid,when=report.when,outcome=report.outcome))
def pytest_sessionfinish(session,exitstatus):
    with open(os.environ['RWX_RESULT'],'w') as f: json.dump(dict(exitstatus=int(exitstatus),reports=reports),f)
'''


def canonical_environment(lock):
    reasons=[]
    if platform.system()!='Linux' or platform.machine()!='x86_64' or sys.version_info[:2]!=(3,13):
        reasons.append('platform_or_python_mismatch')
    for line in Path(lock).read_text().splitlines():
        if '==' not in line or line.startswith('#'): continue
        name,version=line.strip().split('==',1)
        try: actual=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: actual=None
        if actual!=version: reasons.append('dependency:'+name)
    return reasons


class PatchedTree:
    def __init__(self, source, patch_text, max_bytes=55*1024*1024):
        self.source=Path(source); self.patch_text=patch_text; self.max_bytes=max_bytes
    def __enter__(self):
        from blast.patches import parse_patch, apply_change
        self.temp=tempfile.TemporaryDirectory(prefix='rwx-validate-')
        self.path=Path(self.temp.name)/'source'; self.path.mkdir()
        try:
            size=0
            for folder in ('sqlglot','tests'):
                for p in (self.source/folder).rglob('*'):
                    if '.git' in p.parts or '__pycache__' in p.parts or p.suffix in ('.pyc','.so','.pyd'): continue
                    if p.is_symlink(): raise ValueError('symlink in source')
                    if not p.is_file(): continue
                    size+=p.stat().st_size
                    if size>self.max_bytes: raise ValueError('temporary source budget')
                    target=self.path/p.relative_to(self.source);target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(p,target)
            # Preserve actual pytest collection/configuration semantics.
            for name in ('pyproject.toml','pytest.ini','setup.cfg','conftest.py'):
                p=self.source/name
                if p.is_file(): shutil.copyfile(p,self.path/name)
            for change in (parse_patch(self.patch_text) if self.patch_text else []):
                name=change.old_path
                parts=PurePosixPath(name).parts
                if not name or name!=change.new_path or PurePosixPath(name).is_absolute() or '..' in parts:
                    raise ValueError('unsupported structural/path edit')
                p=self.path/name
                if not p.is_file(): raise ValueError('unrepresented source')
                p.write_text(apply_change(p.read_text(),change))
            return self
        except Exception:
            self.temp.cleanup();raise
    def __exit__(self,*args): self.temp.cleanup()


def run_test(tree, nodeid, timeout, adapter=None):
    """A skip, partial execution or harness failure is unresolved, never pass."""
    plugin=tree.path.parent/'rwx_evidence_plugin.py';plugin.write_text(PLUGIN)
    output=tree.path.parent/'result.json';output.unlink(missing_ok=True)
    before=resource.getrusage(resource.RUSAGE_CHILDREN)
    tick=time.monotonic()
    env={**os.environ,'SKIP_INTEGRATION':'0','PYTHONDONTWRITEBYTECODE':'1',
         'PYTHONPATH':str(plugin.parent)+os.pathsep+str(tree.path),'RWX_RESULT':str(output),
         'PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1','HOME':str(tree.path.parent)}
    # Explicitly load timeout; pytest 9 includes native subtest reporting.
    args=[sys.executable,'-B','-m','pytest','-p','rwx_evidence_plugin','-p','pytest_timeout',
          '-p','no:cacheprovider','-q',nodeid]
    if adapter is not None:
        from .fixture_adapter import PLUGIN as ADAPTER_PLUGIN
        (plugin.parent/'rwx_fixture_plugin.py').write_text(ADAPTER_PLUGIN)
        env['RWX_ADAPTER']=json.dumps(adapter)
        env['RWX_ADAPTER_HITS']=str(plugin.parent/'hits.json')
        args[args.index('-q'):args.index('-q')]=['-p','rwx_fixture_plugin']
    with tempfile.TemporaryFile() as logs:
        proc=subprocess.Popen(args,cwd=tree.path,env=env,stdout=logs,stderr=logs,start_new_session=True)
        timed_out=False
        try: proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out=True;os.killpg(proc.pid,signal.SIGKILL);proc.wait()
    after=resource.getrusage(resource.RUSAGE_CHILDREN)
    result={'status':'unresolved','cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
            'wall_seconds':time.monotonic()-tick,'timeout':timed_out,'returncode':proc.returncode}
    if output.exists() and not timed_out:
        data=json.loads(output.read_text());reports=data['reports']
        if any(r['outcome']=='failed' for r in reports): result['status']='confirmed_fail'
        elif proc.returncode==0 and any(r['nodeid']==nodeid and r['when']=='call' and r['outcome']=='passed' for r in reports) and not any(r['outcome']=='skipped' for r in reports):
            result['status']='observed_pass'
    if adapter is not None:
        hits=plugin.parent/'hits.json'
        result['records_visited']=json.loads(hits.read_text()) if hits.exists() else []
        if sorted(result['records_visited'])!=adapter['changed_records']:result['status']='unresolved'
    return result
