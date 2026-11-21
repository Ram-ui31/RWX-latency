"""Research cut point: reuse unchanged tables/reference frames, rerun execution.

Trusted baseline pickle only. This is not a patch-answer cache or a sound
arbitrary-Python analyzer. No capsule output authorizes production omission.
"""
import ast,hashlib,pickle,sys
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def eligible(source,text,manifest):
 from blast.patches import parse_patch,apply_change
 try:
  changes=parse_patch(text)
  if not changes:return False,'empty'
  for edit in changes:
   path=edit.old_path
   if path!=edit.new_path or not path.startswith(('sqlglot/optimizer/','sqlglot/executor/')) or not path.endswith('.py'):return False,'optimizer_or_executor_body_only'
   if path in manifest['protected_files']:return False,'changed_reused_dependency'
   old=(source/path).read_text();new=apply_change(old,edit)
   if ast.dump(ast.parse(old),include_attributes=False)==ast.dump(ast.parse(new),include_attributes=False):return False,'metadata_only_edit'
   from blast.semantics import docstrings_changed
   if docstrings_changed(old,new):return False,'docstring_observer_change'
   a,b=ast.parse(old),ast.parse(new)
   def edit_shape(node):
    if isinstance(node,ast.BoolOp):
     leaves=[]
     def flatten(n):
      if isinstance(n,ast.BoolOp):
       for v in n.values:flatten(v)
      else:leaves.append(edit_shape(n))
     flatten(node);return ('boolean_group',tuple(leaves))
    if isinstance(node,ast.Constant):return ('literal',type(node.value).__name__)
    if isinstance(node,(ast.operator,ast.boolop,ast.cmpop,ast.unaryop)):return ('operator',)
    if isinstance(node,ast.AST):return (type(node).__name__,tuple((k,edit_shape(v)) for k,v in ast.iter_fields(node)))
    if isinstance(node,list):return tuple(edit_shape(v) for v in node)
    return node
   if edit_shape(a)!=edit_shape(b):return False,'requires_new_binding_or_structure'
   before_functions={n.name:ast.dump(n,include_attributes=False) for n in ast.walk(a) if isinstance(n,ast.FunctionDef)}
   for fn in (n for n in ast.walk(b) if isinstance(n,ast.FunctionDef)):
    if before_functions.get(fn.name)==ast.dump(fn,include_attributes=False):continue
    dangerous={'eval','exec','open','getattr','setattr','globals','locals','__import__','sys','os','random','time'}
    if any((isinstance(n,ast.Name) and n.id in dangerous) or (isinstance(n,ast.Attribute) and n.attr in {'__dict__','__class__','__globals__','__code__','__subclasses__','read_text','read_bytes','write_text','write_bytes'}) for n in ast.walk(fn)):return False,'dynamic_or_external_state'

   # Headers, globals, classes, decorators and defaults must remain identical.
   def skeleton(tree):
    import copy
    tree=copy.deepcopy(tree)
    for n in ast.walk(tree):
     if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
      n.body=[ast.Pass()]
    return ast.dump(tree,include_attributes=False)
   if skeleton(a)!=skeleton(b):return False,'initialization_or_signature_change'
   if any(isinstance(n,(ast.Import,ast.ImportFrom,ast.Global,ast.Nonlocal)) for n in ast.walk(b) if getattr(n,'lineno',-1) in edit.coordinates()[1]):return False,'state_or_import_change'
  return True,'supported_body_edit'
 except (ValueError,SyntaxError,OSError):return False,'invalid_context'


def build(source,output):
 source=Path(source).resolve();sys.path.insert(0,str(source))
 print('Checkpoint build: importing executor dependencies',file=sys.stderr,flush=True)
 from tests.test_executor import TestExecutor
 from sqlglot import parse_one,find_tables
 protected=set();owner=str(source)+'/'
 def trace(frame,event,arg):
  if event=='call' and frame.f_code.co_filename.startswith(owner):protected.add(frame.f_code.co_filename[len(owner):])
 case=TestExecutor('test_execute_tpcds');print('Checkpoint build: loading tables and DuckDB references',file=sys.stderr,flush=True);case.setUpClass()
 try:
  records=[];sys.setprofile(trace)
  for meta,sql,expected in case.tpcds_sqls:
   # Original test parses every SQL, even cases that do not execute.
   expression=parse_one(sql)
   reference=case.cached_execute(sql,tpch=False) if meta.get('execute') else None
   subset={t.name:case.tpcds_tables[t.name] for t in find_tables(expression)} if meta.get('execute') else {}
   records.append((meta,sql,expected,reference,sorted(subset)))
  sys.setprofile(None)
  payload={'schema':case.tpcds_tables and __import__('tests.helpers',fromlist=['TPCDS_SCHEMA']).TPCDS_SCHEMA,
           'tables':case.tpcds_tables,'records':records}
  import gzip
  raw=pickle.dumps(payload,protocol=5)
  Path(output).write_bytes(gzip.compress(raw,compresslevel=6) if str(output).endswith('.gz') else raw)
 finally:sys.setprofile(None);case.tearDownClass()
 for table in case.tpcds_tables.values():
  owner=Path(sys.modules[type(table).__module__].__file__).resolve()
  if owner.is_relative_to(source):protected.add(str(owner.relative_to(source)))
 manifest={'environment':environment(),'protected_files':sorted(protected),'source_files':{str(p.relative_to(source)):sha(p) for folder in ('sqlglot','tests') for p in (source/folder).rglob('*.py')},'capsule_sha256':sha(output),'baseline_only':True,'data_files':{str(p.relative_to(source)):sha(p) for p in (source/'tests/fixtures').rglob('*') if p.is_file()},'promotion':False,'table_reset':'fresh baseline deserialization per query'}
 import json
 Path(str(output)+'.json').write_text(json.dumps(manifest,indent=2)+'\n')


def changed_functions(source,text):
 from blast.patches import parse_patch,apply_change
 result=set()
 def functions(tree):
  out={}
  def walk(node,prefix=''):
   for child in ast.iter_child_nodes(node):
    if isinstance(child,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
     name=prefix+child.name
     if isinstance(child,(ast.FunctionDef,ast.AsyncFunctionDef)):out[name]=ast.dump(child,include_attributes=False)
     walk(child,name+('.' if isinstance(child,ast.ClassDef) else '.<locals>.'))
    else:walk(child,prefix)
  walk(tree);return out
 for edit in parse_patch(text):
  old=(source/edit.old_path).read_text();new=apply_change(old,edit)
  a,b=functions(ast.parse(old)),functions(ast.parse(new))
  result.update((edit.old_path,n) for n in set(a)|set(b) if a.get(n)!=b.get(n))
 return sorted(result)


def environment():
 import platform,importlib.metadata
 versions={}
 for name in ('numpy','pandas','duckdb','pytest'):
  try:versions[name]=importlib.metadata.version(name)
  except importlib.metadata.PackageNotFoundError:versions[name]=None
 import os,time
 return {'python':sys.version,'platform':[platform.system(),platform.machine(),list(platform.libc_ver())],'packages':versions,'timezone':list(time.tzname),'TZ':os.environ.get('TZ')}


def load_payload(path):
 import gzip
 raw=Path(path).read_bytes()
 return pickle.loads(gzip.decompress(raw) if raw[:2]==b'\x1f\x8b' else raw)
