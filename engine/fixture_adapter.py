"""Restricted optimizer-fixture replay planning. Shadow evidence only."""
import ast
import json
from pathlib import PurePosixPath
from blast.fixture_contracts import normalize,helpers_fingerprint,EXPECTED_HELPER_FINGERPRINT
from blast.patches import parse_patch,apply_change


def plan(source,text,tests):
    unknown=lambda reason:{'eligible':False,'reason':reason,'omission_authorized':False}
    try:changes=parse_patch(text)
    except ValueError:return unknown('invalid_patch')
    if len(changes)!=1:return unknown('one_fixture_only')
    change=changes[0];path=change.old_path
    p=PurePosixPath(path)
    if p.is_absolute() or '..' in p.parts or path!=change.new_path:return unknown('structural_edit')
    if not path.startswith('tests/fixtures/optimizer/') or not path.endswith('.sql'):return unknown('unsupported_fixture')
    if helpers_fingerprint((source/'tests/helpers.py').read_text())!=EXPECTED_HELPER_FINGERPRINT:return unknown('reader_contract_changed')
    old=(source/path).read_text();new=apply_change(old,change)
    try:a,b=normalize(old,'pairs'),normalize(new,'pairs')
    except (ValueError,IndexError):return unknown('invalid_fixture_stream')
    if len(a)!=len(b):return unknown('record_order_or_count_changed')
    if a!=b and sorted(json.dumps(r,sort_keys=True) for r in a)==sorted(json.dumps(r,sort_keys=True) for r in b):return unknown('record_reordering')
    changed=[i for i,(x,y) in enumerate(zip(a,b)) if x!=y]
    if not changed:return unknown('no_observable_pair_change')
    # Position shifts and native reference comparisons are outside this adapter.
    for records in (a,b):
        for meta,sql,expected in records:
            if str(meta.get('execute','false')).lower() not in ('false','0','none',''):return unknown('native_execution_metadata')
    tree=ast.parse((source/'tests/test_optimizer.py').read_text());eligible=[]
    for cls in tree.body:
        if not isinstance(cls,ast.ClassDef):continue
        for fn in cls.body:
            if not isinstance(fn,ast.FunctionDef) or fn.decorator_list:continue
            body=[n for n in fn.body if not (isinstance(n,ast.Expr) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str))]
            if len(body)!=1 or not isinstance(body[0],ast.Expr) or not isinstance(body[0].value,ast.Call):continue
            call=body[0].value
            if not (isinstance(call.func,ast.Attribute) and isinstance(call.func.value,ast.Name) and call.func.value.id=='self' and call.func.attr=='check_file'):continue
            if not call.args or not isinstance(call.args[0],ast.Constant) or call.args[0].value!=p.stem:continue
            kws={k.arg:k.value for k in call.keywords}
            if any(k is None or k in ('only','execute') and not (isinstance(v,ast.Constant) and v.value is False) for k,v in kws.items()):continue
            nodeid='tests/test_optimizer.py::'+cls.name+'::'+fn.name
            if any(t['id']==nodeid for t in tests):eligible.append(nodeid)
    if len(eligible)!=1:return unknown('ambiguous_or_unsupported_test_body')
    return {'eligible':True,'nodeid':eligible[0],'fixture':path,'relative_fixture':path.removeprefix('tests/fixtures/'),
            'changed_records':changed,'record_count':len(a),'before':[a[i] for i in changed],'after':[b[i] for i in changed],
            'scope':'fixture-only SQL optimization; no native result comparison','omission_authorized':False}


PLUGIN = '''
import json,os
hits=[]
def pytest_collection_modifyitems(session,config,items):
 import tests.test_optimizer as target
 original=target.load_sql_fixture_pairs
 cfg=json.loads(os.environ['RWX_ADAPTER'])
 def selected(filename):
  if filename!=cfg['relative_fixture']:raise RuntimeError('unexpected fixture read')
  records=list(original(filename))
  if len(records)!=cfg['record_count']:raise RuntimeError('record inventory changed')
  for i,record in enumerate(records):
   if i in cfg['changed_records']:
    hits.append(i)
    meta,sql,expected=record
    if not meta.get('title'):
     meta=dict(meta);meta['title']=f'{i+1}, {sql}'
    yield meta,sql,expected
 target.load_sql_fixture_pairs=selected
 # Optional cost experiment. It does not change the emitted test selection.
 if cfg.get('single_worker'):
  executor=target.ProcessPoolExecutor
  def pool(*args,**kwargs):
   kwargs['max_workers']=1
   return executor(*args,**kwargs)
  target.ProcessPoolExecutor=pool

def pytest_sessionfinish(session,exitstatus):
 with open(os.environ['RWX_ADAPTER_HITS'],'w') as f:json.dump(hits,f)
'''
