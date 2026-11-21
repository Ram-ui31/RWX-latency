#!/usr/bin/env python3
"""Measure original pinned baseline validation costs. Never accepts patch answers."""
import argparse,json,subprocess,sys,time,platform,importlib.metadata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from blast.catalog import load_catalog
from blast.indexing import PINNED_COMMIT
from engine.runner import PatchedTree,run_test

def fingerprint():
    versions={}
    for name in ('pytest','pytest-timeout','duckdb','pandas'):
        try:versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:versions[name]=None
    return {'python':sys.version,'platform':[platform.system(),platform.machine(),list(platform.libc_ver())],'packages':versions,'source_pin':PINNED_COMMIT}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--catalog',type=Path,required=True);ap.add_argument('--numbers',type=int,nargs='+',required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--timeout',type=float,default=60);a=ap.parse_args()
 source=a.source.resolve()
 from engine.source_origin import verify
 verify(source)
 tests,ids,ds=load_catalog(a.catalog);report={'fingerprint':fingerprint(),'labels_read':False,'baseline_only':True,'costs':{},'canonical':False,'note':'One local measurement per test. Costs prioritize actions; they are not proofs or hard bounds.'}
 for n in a.numbers:
  tick=time.process_time()
  with PatchedTree(source,'') as tree:r=run_test(tree,tests[n]['id'],a.timeout)
  r['total_cpu_seconds']=r['cpu_seconds']+time.process_time()-tick
  report['costs'][tests[n]['id']]=r
  a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:round(v['total_cpu_seconds'],3) for k,v in report['costs'].items()}))
if __name__=='__main__':main()
