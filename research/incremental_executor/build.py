#!/usr/bin/env python3
import argparse,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from blast.indexing import PINNED_COMMIT
from capsule import build
ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
if a.output.exists():ap.error('fresh output required')
from engine.source_origin import verify
verify(a.source)
build(a.source,a.output)
