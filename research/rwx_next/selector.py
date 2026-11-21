#!/usr/bin/env python3
"""Incremental validation entrypoint. Runtime never reads sample answers."""
import argparse
import gzip
import json
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'rwx'))
from blast.catalog import load_catalog
from blast.indexing import PINNED_COMMIT
from blast.selection import SourceIndex
from blast.scheduling import optimize_schedule,schedule_cost
from engine.changes import analyze
from engine.ipc import consumers as ipc_consumers
from blast.patches import parse_patch
from engine.runner import PatchedTree,canonical_environment,run_test


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-dir',type=Path,required=True)
    ap.add_argument('--index',type=Path,required=True)
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--lock',type=Path,default=HERE.parent/'rwx/sample/requirements.lock')
    ap.add_argument('--cpu-budget',type=float,default=4.0)
    ap.add_argument('--wall-budget',type=float,default=160.0)
    ap.add_argument('--action-limit',type=float,default=2.0)
    ap.add_argument('--startup-estimate',type=float,default=1.0)
    ap.add_argument('--ledger',type=Path)
    ap.add_argument('--observe',action='store_true',help='Research execution while omission promotion is blocked')
    ap.add_argument('--mode',choices=['all','hybrid'],default='all')
    args=ap.parse_args()
    if min(args.cpu_budget,args.wall_budget,args.action_limit,args.startup_estimate)<0:ap.error('negative budget')
    start=time.monotonic();cpu_start=time.process_time()
    tests,ids,durations=load_catalog(args.data_dir/'tests.json')
    ix=SourceIndex(args.index,ids)
    source=args.source.resolve()
    ipc=ipc_consumers(ix.payload,tests) if ix.payload else {}
    pin=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    dirty=subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=no'],text=True)
    if pin!=PINNED_COMMIT or dirty.strip():raise ValueError('Source is not clean pinned commit')
    environment_reasons=canonical_environment(args.lock)
    complete=bool(ix.payload and ix.payload.get('baseline_exit_code')==0 and not ix.unobserved and set(ids).issubset(ix.payload.get('collected',[])))
    # Complete baseline and canonical dependencies are necessary; adapter promotion
    # is deliberately an additional deployment gate, absent from this prototype.
    pass_omission_enabled=False
    ledger={'version':1,'environment_mismatches':environment_reasons,'baseline_complete':complete,
            'pass_omission_enabled':pass_omission_enabled,'adapter_equivalence_validated':False,
            'patches':{},'source_pin':pin}
    spent_children=0.0
    for patch in sorted((args.data_dir/'commits').glob('*.patch')):
        text=patch.read_text()
        selected,reason=ix.select(text,'hybrid') if args.mode=='hybrid' else (set(durations),'all_tests')
        for change in parse_patch(text):
            selected.update(ipc.get(change.old_path,[]))
        entries={n:{'state':'unresolved','reason':reason} for n in selected}
        observations=[]
        original=schedule_cost(optimize_schedule(selected,durations),durations)
        remaining=set(selected)
        while remaining and (pass_omission_enabled or args.observe):
            if time.monotonic()-start>=args.wall_budget:break
            if time.process_time()-cpu_start+spent_children>=args.cpu_budget:break
            current=schedule_cost(optimize_schedule(selected,durations),durations)
            # Actual marginal schedule savings, not individual test duration.
            ranked=[]
            for n in sorted(remaining,key=lambda n:durations[n],reverse=True)[:16]:
                if time.monotonic()-start>=args.wall_budget:break
                benefit=(current-schedule_cost(optimize_schedule(selected-{n},durations),durations))/1000
                if benefit>args.startup_estimate:ranked.append((benefit,n))
            if not ranked:break
            benefit,n=max(ranked);remaining.remove(n)
            budget=args.cpu_budget-(time.process_time()-cpu_start+spent_children)
            limit=min(args.action_limit,budget/2,(args.wall_budget-(time.monotonic()-start))/2)
            if limit<=0.05:break
            tick=time.process_time()
            try:
                with PatchedTree(source,text) as tree:
                    observation=run_test(tree,tests[n]['id'],limit)
            except (ValueError,OSError,UnicodeError) as ex:
                observation={'status':'unresolved','reason':type(ex).__name__,'cpu_seconds':0}
            spent_children+=observation['cpu_seconds']
            observation.update(number=n,marginal_savings_seconds=benefit,parent_action_cpu_seconds=time.process_time()-tick)
            observations.append(observation)
            entries[n]['observation']=observation
            if observation['status']=='confirmed_fail': entries[n]['state']='confirmed_fail'
            elif observation['status']=='observed_pass':
                entries[n]['reason']='local_pass_unpromoted_adapter'
                if pass_omission_enabled:
                    entries[n]['state']='validated_pass';selected.remove(n)
        workers=optimize_schedule(selected,durations)
        print(json.dumps({'commit':patch.stem,'workers':workers},separators=(',',':')),flush=True)
        ledger['patches'][patch.stem]={'retrieval_reason':reason,'selected':sorted(selected),
            'initial_schedule_ms':original,'final_schedule_ms':schedule_cost(workers,durations),
            'observations':observations,'evidence':entries,'change_ir':analyze(source,text)}
    ledger.update(parent_cpu_seconds=time.process_time()-cpu_start,child_cpu_seconds=spent_children,
                  wall_seconds=time.monotonic()-start)
    if args.ledger:args.ledger.write_text(json.dumps(ledger,indent=2)+'\n')
    print(json.dumps({k:v for k,v in ledger.items() if k!='patches'}),file=sys.stderr)


if __name__=='__main__':main()
