#!/usr/bin/env python3
"""Baseline query footprints and original-result verification; no mutation labels."""
import argparse,json,pickle,sys,hashlib
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--capsule',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
source=a.source.resolve();sys.path.insert(0,str(source))
manifest=json.loads(Path(str(a.capsule)+'.json').read_text())
for p,h in {**manifest['source_files'],**manifest.get('data_files',{})}.items():
 if hashlib.sha256((source/p).read_bytes()).hexdigest()!=h:raise ValueError('source mismatch')
from sqlglot import parse_one
from tests.test_executor import mp_execute,initializer
import numpy as np,pandas as pd
from pandas.testing import assert_frame_equal
from capsule import load_payload
payload=load_payload(a.capsule);records=[];active=set();module_files=set();prefix=str(source)+'/'
mon=sys.monitoring;tool=4;mon.use_tool_id(tool,'rwx-query-footprints')
def start(code,offset):
 path=code.co_filename
 if path.startswith(prefix):
  relative=path[len(prefix):]
  active.add((relative,code.co_qualname))
  if code.co_name=='<module>':module_files.add(relative)
 return mon.DISABLE
mon.register_callback(tool,mon.events.PY_START,start)
try:
 for record in payload['records']:
  meta,sql,expected,reference,names=record
  if not meta.get('execute'):records.append((*record,[]));continue
  tables=pickle.loads(pickle.dumps({k:payload['tables'][k] for k in names},protocol=5))
  schema=pickle.loads(pickle.dumps(payload['schema']));expression=pickle.loads(pickle.dumps(parse_one(sql)))
  initializer(schema,tables);active=set();mon.restart_events();mon.set_events(tool,mon.events.PY_START)
  result=mp_execute(expression,meta)
  mon.set_events(tool,0)
  actual=pd.DataFrame(((np.nan if c is None else c for c in row) for row in result.rows),columns=result.columns)
  assert_frame_equal(reference,actual,check_dtype=False,check_index_type=False)
  records.append((*record,sorted(active)))
finally:mon.set_events(tool,0);mon.register_callback(tool,mon.events.PY_START,None);mon.free_tool_id(tool)
payload['records']=records;a.output.write_bytes(__import__('gzip').compress(pickle.dumps(payload,protocol=5),compresslevel=6) if str(a.output).endswith('.gz') else pickle.dumps(payload,protocol=5));manifest['capsule_sha256']=hashlib.sha256(a.output.read_bytes()).hexdigest();manifest['protected_files']=sorted(set(manifest['protected_files'])|module_files);manifest['checkpoint_version']=3;manifest['baseline_query_results_verified']=True
Path(str(a.output)+'.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'records':len(records),'executed':sum(bool(r[0].get('execute')) for r in records),'bytes':a.output.stat().st_size}))

# Baseline-only cold-worker cost calibration. No patch or outcome table is read.
import subprocess,tempfile,resource,os
with tempfile.TemporaryDirectory(prefix='rwx-cold-cost-') as directory:
 result=Path(directory)/'result.json';before=resource.getrusage(resource.RUSAGE_CHILDREN)
 with open(os.devnull,'w') as sink:
  subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('worker.py').resolve()),'--source',str(source),'--capsule',str(a.output.resolve()),'--result',str(result)],check=True,stdout=sink,stderr=sink,timeout=60)
 after=resource.getrusage(resource.RUSAGE_CHILDREN);observation=json.loads(result.read_text())
 if observation['status']!='observed_pass':raise ValueError('Cold checkpoint baseline did not validate')
 manifest['baseline_replay_cpu_seconds']=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime
 Path(str(a.output)+'.json').write_text(json.dumps(manifest,indent=2)+'\n')
