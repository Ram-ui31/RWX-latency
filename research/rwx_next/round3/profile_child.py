#!/usr/bin/env python3
"""Baseline-only tracing of child Python execution for one original test."""
import argparse,gzip,json,os,subprocess,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parents[1];sys.path[:0]=[str(HERE),str(HERE.parent/'rwx')]
from merge_profiles import unpack
from blast.compact import pack_contexts
from blast.catalog import load_catalog
HOOK='''import sys,os,atexit,json
root=os.environ['RWX_TRACE_ROOT'];calls={};modules=set()
def trace(frame,event,arg):
 if event=='call':
  file=frame.f_code.co_filename
  if file.startswith(root+'/'):
   rel=file[len(root)+1:]
   if rel.startswith(('sqlglot/','tests/')):
    calls.setdefault(rel,set()).add(frame.f_code.co_firstlineno)
    modules.add(rel)
 return trace
if sys.argv[0]=='-c':
 sys.setprofile(trace)
 def finish():
  sys.setprofile(None)
  with open(os.environ['RWX_TRACE_OUT']+'/'+str(os.getpid())+'.json','w') as f:json.dump({'calls':{p:sorted(v) for p,v in calls.items()},'modules':sorted(modules)},f)
 atexit.register(finish)
'''
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--index',type=Path,required=True);ap.add_argument('--catalog',type=Path,required=True);ap.add_argument('--nodeid',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 if a.output.exists():ap.error('fresh output required')
 tests,ids,_=load_catalog(a.catalog)
 if a.nodeid not in ids:raise ValueError('unknown nodeid')
 with gzip.open(a.index,'rt') as f:p=unpack(json.load(f))
 source=a.source.resolve()
 # Confirm every mapped application file before trusting original test execution.
 import hashlib
 for name,info in p['files'].items():
  if hashlib.sha256((source/name).read_bytes()).hexdigest()!=info['sha256']:raise ValueError('source mismatch')
 with tempfile.TemporaryDirectory(prefix='rwx-child-profile-') as d:
  temp=Path(d);(temp/'sitecustomize.py').write_text(HOOK)
  env={**os.environ,'PYTHONPATH':str(temp)+os.pathsep+str(source),'PATH':str(Path(sys.executable).parent)+os.pathsep+os.environ['PATH'],'RWX_TRACE_ROOT':str(source),'RWX_TRACE_OUT':str(temp),'PYTHONDONTWRITEBYTECODE':'1','SKIP_INTEGRATION':'0'}
  r=subprocess.run([sys.executable,'-m','pytest','-p','no:cacheprovider','-q',a.nodeid],cwd=source,env=env,capture_output=True,text=True,timeout=45)
  records=[json.loads(x.read_text()) for x in temp.glob('*.json')]
  if r.returncode or not records:raise ValueError('Baseline child test did not pass or produced no traces: '+r.stdout[-1000:]+r.stderr[-1000:])
  for record in records:
   for path,lines in record['calls'].items():
    for line in lines:
     rows=p.setdefault('calls',{}).setdefault(path,{});rows[str(line)]=sorted(set(rows.get(str(line),[]))|{a.nodeid})
   for path in record['modules']:
    rows=p.setdefault('module_users',{});rows[path]=sorted(set(rows.get(path,[]))|{a.nodeid})
  p['untraced']=[x for x in p['untraced'] if x!=a.nodeid];p['outcomes'][a.nodeid]=['passed']
  # Deliberately no claim of statement coverage or arbitrary subprocess support.
  p['line_incomplete']=sorted(set(p.get('line_incomplete',[]))|{a.nodeid})
  p['child_trace_evidence']={'test':a.nodeid,'processes':len(records),'files':sorted(set().union(*(set(r['calls']) for r in records))),'canonical':False,'limitation':'Python -c subprocess only; dynamic input, native and non-Python processes are not covered'}
 pack_contexts(p)
 with gzip.open(a.output,'wt') as f:json.dump(p,f,separators=(',',':'))
 print(json.dumps(p['child_trace_evidence']))
if __name__=='__main__':main()
