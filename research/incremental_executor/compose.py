#!/usr/bin/env python3
"""Compose checkpoint validation with upstream selections, research output only."""
import argparse,json,sys,time,resource,subprocess,os,signal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from capsule import eligible,sha,environment,changed_functions
from engine.runner import PatchedTree
from engine.verification_budget import gate
from blast.catalog import load_catalog
from blast.scheduling import optimize_schedule,schedule_cost
ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--capsule',type=Path,required=True);ap.add_argument('--data',type=Path,required=True);ap.add_argument('--upstream',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--wall-budget',type=float,default=95);ap.add_argument('--report',type=Path,required=True);a=ap.parse_args()
wall=time.monotonic();start=time.process_time();child0=resource.getrusage(resource.RUSAGE_CHILDREN);source=a.source.resolve();m=json.loads(Path(str(a.capsule)+'.json').read_text())
if m['environment']!=environment():raise ValueError('environment mismatch')
for p,h in {**m['source_files'],**m.get('data_files',{})}.items():
 if sha(source/p)!=h:raise ValueError('reused source/data mismatch')
tests,ids,ds=load_catalog(a.data/'tests.json');target=ids['tests/test_executor.py::TestExecutor::test_execute_tpcds'];results=[];observations={}
for row in map(json.loads,a.upstream.read_text().splitlines()):
 selected={n for w in row['workers'] for n in w};c=row['commit']
 if target in selected:
  text=(a.data/'commits'/f'{c}.patch').read_text();ok,reason=eligible(source,text,m)
  gain=(schedule_cost(optimize_schedule(selected,ds),ds)-schedule_cost(optimize_schedule(selected-{target},ds),ds))/1000
  r=resource.getrusage(resource.RUSAGE_CHILDREN);spent=time.process_time()-start+r.ru_utime+r.ru_stime-child0.ru_utime-child0.ru_stime
  decision=gate(gain,20-spent,{'status':'observed_pass','total_cpu_seconds':m.get('baseline_replay_cpu_seconds',float('inf'))})
  if ok and decision['allowed'] and time.monotonic()-wall<a.wall_budget:
   with PatchedTree(source,text) as tree:
    result=tree.path.parent/'result.json';changed=tree.path.parent/'changed.json';changed.write_text(json.dumps(changed_functions(source,text)))
    with open(os.devnull,'w') as sink:
     proc=subprocess.Popen([sys.executable,'-B',str(Path(__file__).with_name('worker.py').resolve()),'--source',str(tree.path),'--capsule',str(a.capsule.resolve()),'--result',str(result),'--changed',str(changed)],stdout=sink,stderr=sink,start_new_session=True,env={**os.environ,'SKIP_INTEGRATION':'0','PYTHONDONTWRITEBYTECODE':'1'})
     try:proc.wait(timeout=max(0.01,min(30,a.wall_budget-(time.monotonic()-wall))))
     except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
    obs=json.loads(result.read_text()) if result.exists() else {'status':'unresolved'}
   observations[c]=obs
   if obs['status']=='observed_pass':selected.remove(target)
  else:observations[c]={'status':'not_run','reason':reason if not ok else decision['reason']}
 results.append({'commit':c,'workers':optimize_schedule(selected,ds)})
a.output.write_text(''.join(json.dumps(r)+'\n' for r in results));r=resource.getrusage(resource.RUSAGE_CHILDREN)
report={'shadow_only':True,'production_omission_authorized':False,'labels_read':False,'cpu_seconds':time.process_time()-start+r.ru_utime+r.ru_stime-child0.ru_utime-child0.ru_stime,'observations':observations}
a.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
