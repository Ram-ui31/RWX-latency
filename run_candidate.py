#!/usr/bin/env python3
"""Protocol entrypoint for the explicitly experimental checkpoint candidate."""
import json,os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def run(args):
 p=subprocess.run([sys.executable,'-B',*map(str,args)],stdout=subprocess.PIPE,stderr=sys.stderr,text=True)
 if p.returncode:raise RuntimeError('candidate stage failed')
 if p.stdout:print(p.stdout,file=sys.stderr,end='')

def main():
 data=Path(os.environ.get('DATA_DIR','/data'));source=ROOT/'pinned-source'
 with tempfile.TemporaryDirectory(prefix='rwx-batch-') as folder:
  folder=Path(folder);upstream=folder/'upstream.jsonl';final=folder/'final.jsonl'
  run([ROOT/'research/tail_verifier/evaluate.py','--source',source,'--data',data,'--cost-profile',ROOT/'assets/verification-costs.json','--report',folder/'tail.json','--predictions',upstream,'--max-actions','5','--min-saving','2','--cpu-budget','20','--action-timeout','8','--wall-budget','45'])
  try:
   run([ROOT/'research/incremental_executor/compose.py','--source',source,'--capsule',ROOT/'assets/checkpoints.pkl.gz','--data',data,'--upstream',upstream,'--output',final,'--report',folder/'checkpoint.json','--wall-budget','95'])
  except (RuntimeError,OSError):final=upstream
  sys.stdout.write(final.read_text());sys.stdout.flush()

if __name__=='__main__':
 try:main()
 except (RuntimeError,OSError,ValueError) as ex:
  print('Experimental candidate failed; using reference selector: '+str(ex),file=sys.stderr)
  p=subprocess.run([sys.executable,'-B',str(ROOT/'selector.py')]);raise SystemExit(p.returncode)
