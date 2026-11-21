#!/usr/bin/env python3
"""Build exact fixture records and byte hashes from clean pinned baseline only."""
import argparse,gzip,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'rwx'))
from blast.indexing import PINNED_COMMIT
from engine.core import fixture_inventory

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    if args.output.exists():ap.error('Use a fresh output')
    pin=subprocess.check_output(['git','-C',str(args.source),'rev-parse','HEAD'],text=True).strip()
    dirty=subprocess.check_output(['git','-C',str(args.source),'status','--porcelain','--untracked-files=no'],text=True)
    if pin!=PINNED_COMMIT or dirty.strip():raise ValueError('Expected clean pinned source')
    evidence=fixture_inventory(args.source);evidence.update(version=1,source_pin=pin,labels_read=False,consumer_graph_complete=False)
    with gzip.open(args.output,'wt') as f:json.dump(evidence,f,separators=(',',':'))
    print(json.dumps({'fixtures':len(evidence['fixtures']),'bytes':args.output.stat().st_size,'labels_read':False}))
if __name__=='__main__':main()
