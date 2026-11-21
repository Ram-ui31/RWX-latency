#!/usr/bin/env python3
"""Competition entrypoint: output only one compact JSON object per patch."""
import argparse
from collections import Counter
from functools import lru_cache
import json
import os
from pathlib import Path
import sys
import time
from blast.catalog import load_catalog
from blast.scheduling import optimize_schedule
from blast.selection import SourceIndex
from blast.patches import parse_patch
from engine.ipc import consumers as ipc_consumers


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,default=Path(os.environ.get('DATA_DIR','/data')))
    parser.add_argument('--index',type=Path,default=Path(__file__).resolve().parent/'maps/source-index.json.gz')
    parser.add_argument('--mode',choices=['all','module','coverage','hybrid','impact'],default=os.environ.get('RWX_SELECTION_MODE','all'))
    args=parser.parse_args()
    start=time.process_time()
    tests, ids, durations=load_catalog(args.data_dir/'tests.json')
    index=SourceIndex(args.index if args.mode!='all' else None,ids)
    reasons=Counter()
    ipc=ipc_consumers(index.payload,tests) if index.payload else {}
    @lru_cache(maxsize=128)
    def schedule(numbers):
        return optimize_schedule(numbers,durations)
    patches=sorted((args.data_dir/'commits').glob('*.patch'))
    if not patches: raise ValueError('No .patch files found')
    for patch in patches:
        if args.mode=='all':
            selected,reason=set(durations),'all_tests_baseline'
        else:
            try:
                selected,reason=index.select(patch.read_text(encoding='utf-8'),args.mode)
            except (UnicodeError,OSError):
                selected,reason=set(durations),'unreadable_patch_fallback'
        for change in parse_patch(patch.read_text(encoding='utf-8')):
            selected.update(ipc.get(change.old_path,[]))
        workers=schedule(tuple(sorted(selected)))
        print(json.dumps(dict(commit=patch.stem,workers=workers),separators=(',',':')),flush=True)
        reasons[reason]+=1
    print(json.dumps(dict(mode=args.mode,patches=len(patches),tests=len(tests),index=index.reason,decisions=dict(reasons),selector_cpu_seconds=round(time.process_time()-start,6))),file=sys.stderr)

if __name__=='__main__':
    try: main()
    except (ValueError,KeyError,OSError) as error:
        print('Selector failed: '+str(error),file=sys.stderr)
        raise SystemExit(1)
