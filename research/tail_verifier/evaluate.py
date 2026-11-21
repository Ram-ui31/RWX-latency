#!/usr/bin/env python3
"""Cost-first original-test verification experiment. No answers used in decisions.

Counterfactual selections are research output, not promoted certificates.
"""
import argparse,json,resource,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from blast.catalog import load_catalog
from blast.indexing import PINNED_COMMIT
from blast.selection import SourceIndex
from blast.scheduling import optimize_schedule,schedule_cost
from blast.patches import parse_patch
from engine.selection import adaptive_select
from engine.ipc import consumers
from engine.runner import PatchedTree,run_test
from engine.verification_budget import gate

def best_action(selected,durations,excluded):
    base=schedule_cost(optimize_schedule(selected,durations),durations)
    actions=[]
    # Bound analysis work independently of the size of the suite.
    for n in sorted(selected-excluded,key=lambda n:-durations[n])[:12]:
        gain=(base-schedule_cost(optimize_schedule(selected-{n},durations),durations))/1000
        if gain>0:actions.append((gain,n))
    return max(actions,default=(0,None))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--data',type=Path,required=True);ap.add_argument('--report',type=Path,required=True);ap.add_argument('--predictions',type=Path,required=True);ap.add_argument('--wall-budget',type=float,default=45);ap.add_argument('--cpu-budget',type=float,default=60);ap.add_argument('--action-timeout',type=float,default=8);ap.add_argument('--min-saving',type=float,default=5);ap.add_argument('--max-actions',type=int,default=5);ap.add_argument('--cost-profile',type=Path);ap.add_argument('--observations',type=Path);ap.add_argument('--settings',type=Path);ap.add_argument('--contracts',type=Path);ap.add_argument('--allow-uncalibrated-experiment',action='store_true');a=ap.parse_args()
 if min(a.cpu_budget,a.min_saving,a.max_actions)<0 or a.action_timeout<=0:ap.error('invalid budget')
 start=time.process_time();wall=time.monotonic();usage=resource.getrusage(resource.RUSAGE_CHILDREN)
 def cpu():
  r=resource.getrusage(resource.RUSAGE_CHILDREN);return time.process_time()-start+r.ru_utime+r.ru_stime-usage.ru_utime-usage.ru_stime
 source=a.source.resolve()
 from engine.source_origin import verify
 verify(source)
 tests,ids,ds=load_catalog(a.data/'tests.json');index=SourceIndex(ROOT/'maps/source-index.json.gz',ids)
 observer=None
 if a.observations:
  from research.observations.choose import Observations
  observer=Observations(a.observations,index,a.settings,tests,a.contracts)
 else:
  ipc=consumers(index.payload,tests)
 rows={};texts={}
 for patch in sorted((a.data/'commits').glob('*.patch')):
  text=patch.read_text()
  try:
   if observer:
    selected,reason=observer.select(text),'baseline_observations'
   else:
    selected,reason=adaptive_select(index,text)
    for e in parse_patch(text):selected.update(ipc.get(e.old_path,[]))
  except (ValueError,SyntaxError,OSError):
   selected,reason=set(ds),'unsupported_patch'
  hazard=bool(observer and observer.contracts and observer.contracts.import_hazard)
  texts[patch.stem]=text;rows[patch.stem]={'initial':sorted(selected),'selected':set(selected),'reason':reason,'import_hazard':hazard,'actions':[],'tried':set(selected) if hazard else set()}
 actions=0
 cost_data={}
 cost_profile_status='missing'
 if a.cost_profile:
  from calibrate import fingerprint
  profile=json.loads(a.cost_profile.read_text())
  if profile.get('baseline_only') and profile.get('fingerprint')==fingerprint():
   cost_data=profile['costs'];cost_profile_status='local_fingerprint_match'
  else:cost_profile_status='mismatch'
 # A test without a passing baseline calibration cannot authorize an action.
 calibrated={ids[node] for node,record in cost_data.items() if node in ids and record.get('status')=='observed_pass'}
 skipped={}
 while actions<a.max_actions and cpu()<a.cpu_budget and time.monotonic()-wall<a.wall_budget:
  choices=[];rejected_this_round=False
  for c,r in rows.items():
   if observer and not a.allow_uncalibrated_experiment:
    available=(r['selected'] & calibrated) - r['tried']
    if not available:continue
    gain,n=best_action(r['selected'],ds,r['selected']-available)
   else:
    gain,n=best_action(r['selected'],ds,r['tried'])
   if n is not None and gain>=a.min_saving:
    decision=gate(gain,a.cpu_budget-cpu(),cost_data.get(tests[n]['id']))
    if not decision['allowed'] and not a.allow_uncalibrated_experiment:
     skipped[c]={'number':n,**decision};r['tried'].add(n);rejected_this_round=True;continue
    choices.append((gain,c,n))
  if not choices:
   if rejected_this_round:continue
   break
  gain,c,n=max(choices);r=rows[c];r['tried'].add(n);tick=cpu()
  try:
   with PatchedTree(source,texts[c]) as tree:obs=run_test(tree,tests[n]['id'],min(a.action_timeout,max(0.01,a.wall_budget-(time.monotonic()-wall))))
  except (ValueError,OSError) as ex:obs={'status':'unresolved','reason':type(ex).__name__}
  cost=cpu()-tick;obs.update(number=n,nodeid=tests[n]['id'],potential_saving=gain,action_total_cpu=cost)
  if obs['status']=='observed_pass':r['selected'].remove(n)
  obs['realized_saving']=gain if obs['status']=='observed_pass' else 0
  obs['net_saving']=obs['realized_saving']-cost;r['actions'].append(obs);actions+=1
  # A timed-out or uneconomical verification does not justify repeated actions
  # in this same domain during this batch. Keep all remaining tests unchanged.
  if obs['status']=='unresolved' or cost>gain:
   r['tried'].update(r['selected'])
 outputs=[]
 for c,r in rows.items():
  outputs.append({'commit':c,'workers':optimize_schedule(r['selected'],ds)})
  r['final_schedule_seconds']=schedule_cost(outputs[-1]['workers'],ds)/1000
  r['selected']=sorted(r['selected']);r['tried']=sorted(r['tried'])
 report={'status':'noncanonical_counterfactual_only','labels_read':False,'omission_promoted':False,'cpu_seconds':cpu(),'wall_seconds':time.monotonic()-wall,'actions':actions,'cost_profile_status':cost_profile_status,'cost_rejections':skipped,'patches':rows,'budget_note':'Soft evaluation CPU budget; a running process-tree action can overshoot. Original selector remains unchanged.'}
 a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2)+'\n');a.predictions.write_text(''.join(json.dumps(x)+'\n' for x in outputs))
 print(json.dumps({k:v for k,v in report.items() if k!='patches'}))
if __name__=='__main__':main()
