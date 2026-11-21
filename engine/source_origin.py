"""Verify a clean pinned Git checkout or the build's hashed immutable archive."""
import hashlib,json,subprocess
from pathlib import Path
from blast.indexing import PINNED_COMMIT

def verify(source):
 source=Path(source).resolve();manifest=source/'.source-origin.json'
 if manifest.exists():
  m=json.loads(manifest.read_text())
  if m.get('source_commit')!=PINNED_COMMIT or m.get('url')!='https://github.com/tobymao/sqlglot/archive/'+PINNED_COMMIT+'.tar.gz':raise ValueError('source origin mismatch')
  for name,h in m['files'].items():
   p=source/name
   if p.is_symlink() or not p.resolve().is_relative_to(source) or hashlib.sha256(p.read_bytes()).hexdigest()!=h:raise ValueError('baseline file changed')
 else:
  if subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()!=PINNED_COMMIT:raise ValueError('pin mismatch')
  if subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=no'],text=True).strip():raise ValueError('dirty source')
