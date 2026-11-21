#!/usr/bin/env python3
"""Replay complete query assertions; skip unchanged setup and native references."""
import argparse,json,pickle,sys,time,hashlib
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--capsule',type=Path,required=True);ap.add_argument('--result',type=Path,required=True);ap.add_argument('--changed',type=Path);a=ap.parse_args()
sys.path.insert(0,str(a.source.resolve()))
manifest=json.loads(Path(str(a.capsule)+'.json').read_text())
from capsule import environment,load_payload
if manifest.get('environment')!=environment():raise ValueError('checkpoint environment mismatch')
if hashlib.sha256(a.capsule.read_bytes()).hexdigest()!=manifest['capsule_sha256']:raise ValueError('capsule hash mismatch')
from sqlglot import parse_one
from tests.test_executor import mp_execute,initializer,TestExecutor
from pandas.testing import assert_frame_equal
import pandas as pd,numpy as np
# Only trusted baseline artifacts created by build.py may be deserialized.
payload=load_payload(a.capsule)
case=TestExecutor('test_execute_tpcds');failures=[];unknown=[];executed=0;reused=0;attempted=0
changed={tuple(v) for v in json.loads(a.changed.read_text())} if a.changed else None
for i,record in enumerate(payload['records']):
 meta,sql,expected,reference,*checkpoint=record
 try:
  import re
  if re.search(r'\b(CURRENT_DATE|CURRENT_TIME|CURRENT_TIMESTAMP|NOW|RAND|RANDOM|UUID|CURRENT_USER)\b',sql,re.I):
   unknown.append({'query':i,'reason':'nondeterministic_input'});continue
  if changed is not None and len(checkpoint)>1 and checkpoint[1] and changed.isdisjoint({tuple(v) for v in checkpoint[1]}):
   reused+=1;continue
  expression=parse_one(sql)
  # Retain the original queue's Expr serialization boundary.
  expression=pickle.loads(pickle.dumps(expression,protocol=5))
  if not meta.get('execute'):continue
  subset={k:payload['tables'][k] for k in checkpoint[0]} if checkpoint else payload['tables']
  tables=pickle.loads(pickle.dumps(subset,protocol=5));schema=pickle.loads(pickle.dumps(payload['schema']))
  before=pickle.dumps({k:(v.columns,v.rows) for k,v in tables.items()},protocol=5)
  schema_before=pickle.dumps(schema,protocol=5)
  initializer(schema,tables);attempted+=1;table=mp_execute(expression,meta)
  if before!=pickle.dumps({k:(v.columns,v.rows) for k,v in tables.items()},protocol=5) or schema_before!=pickle.dumps(schema,protocol=5):unknown.append({'query':i,'reason':'input_data_mutated'})
  if table is None:unknown.append({'query':i,'reason':'missing_result'});continue
  actual=pd.DataFrame(((np.nan if c is None else c for c in r) for r in table.rows),columns=table.columns)
  assert_frame_equal(reference,actual,check_dtype=False,check_index_type=False)
  executed+=1
 except Exception as ex:
  failures.append({'query':i,'exception':type(ex).__name__,'message':str(ex)[:300]})
  break
status='observed_fail' if failures else 'unresolved' if unknown else 'observed_pass'
a.result.write_text(json.dumps({'status':status,'executed_queries':executed,'evaluated_queries':attempted,'reused_queries':reused,'failures':failures,'unknown':unknown,'total_records':len(payload['records']),'production_omission_authorized':False},indent=2)+'\n')
