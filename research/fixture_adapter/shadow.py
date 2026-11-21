#!/usr/bin/env python3
"""Run original optimizer tests and restricted record replay. Never omit tests."""
import argparse,json,subprocess,sys,time,resource
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from blast.catalog import load_catalog
from blast.indexing import PINNED_COMMIT
from blast.scheduling import optimize_schedule,schedule_cost
from blast.selection import SourceIndex
from engine.selection import adaptive_select
from engine.ipc import consumers
from engine.fixture_adapter import plan
from engine.runner import PatchedTree,run_test

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,required=True);ap.add_argument('--data',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--timeout',type=float,default=30);ap.add_argument('--limit',type=int,default=0);ap.add_argument('--cpu-budget',type=float,default=180.0);a=ap.parse_args()
 if a.cpu_budget<0 or a.timeout<=0 or a.limit<0:ap.error('budgets/limit must be nonnegative and timeout positive')
 cpu_start=time.process_time();child_start=resource.getrusage(resource.RUSAGE_CHILDREN)
 def spent():
  r=resource.getrusage(resource.RUSAGE_CHILDREN);return time.process_time()-cpu_start+r.ru_utime+r.ru_stime-child_start.ru_utime-child_start.ru_stime
 source=a.source.resolve()
 if subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()!=PINNED_COMMIT:raise ValueError('pin mismatch')
 if subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=no'],text=True).strip():raise ValueError('dirty baseline')
 tests,ids,durations=load_catalog(a.data/'tests.json');index=SourceIndex(ROOT/'maps/source-index.json.gz',ids);ipc=consumers(index.payload,tests)
 report={'shadow_only':True,'labels_read':False,'omission_authorized':False,'cases':{},'baseline_checks':{},'source_pin':PINNED_COMMIT};count=0
 for file in sorted((a.data/'commits').glob('*.patch')):
  text=file.read_text();item=plan(source,text,tests);report['cases'][file.stem]={'plan':item}
  if not item['eligible']:continue
  if spent()>=a.cpu_budget:report['cases'][file.stem]['not_executed']='evaluation_cpu_budget';continue
  if a.limit and count>=a.limit:report['cases'][file.stem]['not_executed']='limit';continue
  count+=1;node=item['nodeid']
  def execute(patch,adapter=None):
   tick=time.process_time()
   with PatchedTree(source,patch) as tree:r=run_test(tree,node,a.timeout,adapter=adapter)
   r['parent_cpu_seconds']=time.process_time()-tick
   return r
  if node not in report['baseline_checks']:report['baseline_checks'][node]=execute('')
  row=report['cases'][file.stem]
  if report['baseline_checks'][node]['status']!='observed_pass':row['blocked']='baseline_did_not_pass';continue
  row['whole_test']=execute(text)
  row['filtered_original_pool']=execute(text,item)
  row['filtered_single_worker']=execute(text,{**item,'single_worker':True})
  reference=row['whole_test']['status'];row['agreement']={k:reference in ('observed_pass','confirmed_fail') and row[k]['status']==reference for k in ('filtered_original_pool','filtered_single_worker')}
  selected,_=adaptive_select(index,text)
  from blast.patches import parse_patch
  for edit in parse_patch(text):selected.update(ipc.get(edit.old_path,[]))
  n=ids[node];before=schedule_cost(optimize_schedule(selected,durations),durations);after=schedule_cost(optimize_schedule(selected-{n},durations),durations)
  row['possible_schedule_saving_seconds']=(before-after)/1000
  row['realizable_schedule_saving_seconds']=(before-after)/1000 if reference=='observed_pass' else 0.0
  row['optimistic_net_saving_seconds']={k:row['possible_schedule_saving_seconds']-row[k]['cpu_seconds']-row[k]['parent_cpu_seconds'] for k in ('filtered_original_pool','filtered_single_worker')}
  row['note']='Savings assume a validated pass permits omission; a detected failure cannot earn this saving. Oracle reference CPU is evaluation-only, not a deployment action.'
  a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
 report['measured_evaluation_cpu_seconds']=spent()
 a.output.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'eligible':sum(r['plan']['eligible'] for r in report['cases'].values()),'executed':count,'agreements':[r['agreement'] for r in report['cases'].values() if 'agreement' in r],'omission_authorized':False}))
if __name__=='__main__':main()
