#!/usr/bin/env python3
"""Protocol entrypoint for baseline observations or checkpoint validation."""
import json,os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def run(args):
 p=subprocess.run([sys.executable,'-B',*map(str,args)],stdout=subprocess.PIPE,stderr=sys.stderr,text=True)
 if p.returncode:raise RuntimeError('candidate stage failed')
 if p.stdout:print(p.stdout,file=sys.stderr,end='')

def main():
 import time
 started=time.monotonic()
 data=Path(os.environ.get('DATA_DIR','/data'));source=ROOT/'pinned-source'
 # The run limit is about 4.5 wall seconds per commit (3 min for ~40, 4.5 min for ~60).
 n=max(1,len(list((data/'commits').glob('*.patch'))))
 deadline=float(os.environ.get('RWX_SECONDS_PER_COMMIT','4.5'))*n
 def left():return deadline-(time.monotonic()-started)
 with tempfile.TemporaryDirectory(prefix='rwx-batch-') as folder:
  folder=Path(folder);upstream=folder/'upstream.jsonl';final=folder/'final.jsonl'
  observations=os.environ.get('RWX_OBSERVATIONS')
  settings=os.environ.get('RWX_TYPED_SETTINGS')
  contracts=os.environ.get('RWX_ARGUMENT_CONTRACTS')
  run([ROOT/'research/tail_verifier/evaluate.py','--source',source,'--data',data,'--cost-profile',ROOT/'assets/verification-costs.json','--report',folder/'tail.json','--predictions',upstream,'--max-actions',os.environ.get('RWX_TAIL_ACTIONS','5'),'--min-saving','2','--cpu-budget',os.environ.get('RWX_TAIL_CPU','20'),'--action-timeout','8','--wall-budget','45',*(['--observations',observations] if observations else []),*(['--settings',settings] if settings else []),*(['--contracts',contracts] if contracts else [])])
  if observations:
   memo=folder/'memo.jsonl'
   if os.environ.get('RWX_NATIVE_ORACLE') and os.environ.get('RWX_NATIVE_MEMO_ENABLE','1')=='1':
    try:
     run([ROOT/'research/native_oracle/run.py','--source',source,'--data',data,'--cache',os.environ['RWX_NATIVE_ORACLE'],'--contracts',contracts,'--readers',settings,'--upstream',upstream,'--output',memo,'--selection-report',folder/'tail.json','--report',folder/'memo.json','--budget','20','--wall-budget','30'])
     upstream=memo
    except (RuntimeError,OSError,ValueError):pass
   if os.environ.get('RWX_INFER')=='1' and (ROOT/'assets/infer-costs.json').is_file() and left()>0.5*deadline:
    try:
     run([ROOT/'research/infer/run.py','--source',source,'--data',data,'--upstream',upstream,'--output',final,'--report',folder/'infer.json','--costs',ROOT/'assets/infer-costs.json','--maxnodes',ROOT/'assets/maxnodes.json','--budget',os.environ.get('RWX_INFER_CPU',str(1.5*n)),'--wall-budget',os.environ.get('RWX_INFER_WALL',str(min(1.6*n,left()-0.35*deadline)))])
     upstream=final;final=folder/'final2.jsonl'
    except (RuntimeError,OSError):pass
   if os.environ.get('RWX_GROUP_VERIFY')=='1' and left()>0.3*deadline:
    try:
     run([ROOT/'research/group_verifier/run.py','--source',source,'--data',data,'--upstream',upstream,'--output',final,'--report',folder/'groups.json','--selection-report',folder/'tail.json','--minimal','--cheap-modules','--seconds-factor','0.1','--budget',os.environ.get('RWX_GROUP_CPU','10'),'--wall-budget',os.environ.get('RWX_GROUP_WALL',str(min(30.0,left()-0.2*deadline))),*(['--cost-profile',ROOT/'assets/group-costs.json'] if os.environ.get('RWX_GROUP_PROFILE','1')=='1' and (ROOT/'assets/group-costs.json').is_file() else [])])
    except (RuntimeError,OSError):final=upstream
   else:final=upstream
   sys.stdout.write(final.read_text());sys.stdout.flush();return
  try:
   run([ROOT/'research/incremental_executor/compose.py','--source',source,'--capsule',ROOT/'assets/checkpoints.pkl.gz','--data',data,'--upstream',upstream,'--output',final,'--report',folder/'checkpoint.json','--wall-budget','95'])
  except (RuntimeError,OSError):final=upstream
  sys.stdout.write(final.read_text());sys.stdout.flush()

if __name__=='__main__':
 try:main()
 except (RuntimeError,OSError,ValueError) as ex:
  print('Experimental candidate failed; using reference selector: '+str(ex),file=sys.stderr)
  p=subprocess.run([sys.executable,'-B',str(ROOT/'selector.py')]);raise SystemExit(p.returncode)
