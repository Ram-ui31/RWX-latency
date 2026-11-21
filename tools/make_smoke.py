"""Synthetic comment-only change for offline entrypoint/protocol testing."""
import difflib,json,sys
from pathlib import Path
source=Path(sys.argv[1]).read_text();destination=Path(sys.argv[2]);(destination/'commits').mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[1]
(destination/'tests.json').write_bytes((root/'build-catalog.json').read_bytes())
path='sqlglot/optimizer/eliminate_ctes.py';new=source+'\n# Synthetic runtime smoke check.\n'
patch='diff --git a/'+path+' b/'+path+'\n'+''.join(difflib.unified_diff(source.splitlines(True),new.splitlines(True),fromfile='a/'+path,tofile='b/'+path))
(destination/'commits/smoke.patch').write_text(patch)
