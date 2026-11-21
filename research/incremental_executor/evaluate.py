#!/usr/bin/env python3
import argparse,json,subprocess,sys,time,resource,os,signal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from capsule import eligible,sha,changed_functions
from engine.runner import PatchedTree
ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--capsule',type=Path,required=True);ap.add_argument('--patches',type=Path,required=True);ap.add_argument('--report',type=Path,required=True);a=ap.parse_args()
source=a.source.resolve();manifest=json.loads(Path(str(a.capsule)+'.json').read_text())
for p,h in {**manifest['source_files'],**manifest.get('data_files',{})}.items():
 if sha(source/p)!=h:raise ValueError('baseline changed: '+p)
rows={}
for patch in [None,*sorted(a.patches.glob('*.patch'))]:
 text=patch.read_text() if patch else '';ok,reason=eligible(source,text,manifest) if patch else (True,'baseline_control')
 name=patch.stem if patch else 'baseline';rows[name]={'eligible':ok,'reason':reason}
 if not ok:continue
 before=resource.getrusage(resource.RUSAGE_CHILDREN);parent=time.process_time();tick=time.monotonic()
 with PatchedTree(source,text) as tree:
  result=tree.path.parent/'result.json'
  changes=tree.path.parent/'changed.json';changes.write_text(json.dumps(changed_functions(source,text) if patch else []))
  extra=['--changed',str(changes)] if patch and manifest.get('checkpoint_version')==3 else []
  with open(os.devnull,'w') as sink:
   p=subprocess.Popen([sys.executable,'-B',str(Path(__file__).with_name('worker.py').resolve()),'--source',str(tree.path),'--capsule',str(a.capsule.resolve()),'--result',str(result),*extra],stdout=sink,stderr=sink,start_new_session=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','SKIP_INTEGRATION':'0'})
   try:p.wait(timeout=30)
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
  observation=json.loads(result.read_text()) if result.exists() else {'status':'unresolved','reason':'worker_error_or_timeout'}
 after=resource.getrusage(resource.RUSAGE_CHILDREN)
 rows[name].update(observation,cpu_seconds=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime+time.process_time()-parent,wall_seconds=time.monotonic()-tick)
 a.report.write_text(json.dumps({'shadow_only':True,'labels_read':False,'cases':rows},indent=2)+'\n')
a.report.write_text(json.dumps({'shadow_only':True,'labels_read':False,'cases':rows},indent=2)+'\n')
print(json.dumps({k:(v.get('status',v['reason']),round(v.get('cpu_seconds',0),3)) for k,v in rows.items()}))
