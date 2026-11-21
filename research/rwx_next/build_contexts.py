#!/usr/bin/env python3
"""Capture actual parent-process optimizer helper bindings; gaps stay explicit."""
import argparse,gzip,json,math,os,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE.parent/'rwx')]
from blast.indexing import PINNED_COMMIT
import subprocess

def encode(x,depth=0):
    if depth>12:return {'unknown':'depth'}
    if x is None or type(x) in (bool,int,str):return x
    if type(x) is float and math.isfinite(x):return x
    if type(x) in (list,tuple) and len(x)<10000:return [encode(v,depth+1) for v in x]
    if type(x) is dict and len(x)<10000 and all(type(k) is str for k in x):return {k:encode(v,depth+1) for k,v in x.items()}
    if callable(x):return {'callable_module':getattr(x,'__module__',None),'callable_qualname':getattr(x,'__qualname__',None)}
    return {'unknown_type':type(x).__name__}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args,tests=ap.parse_known_args()
    source=args.source.resolve()
    if subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()!=PINNED_COMMIT:raise ValueError('pin')
    if subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=no'],text=True).strip():raise ValueError('dirty source')
    sys.path.insert(0,str(source));os.chdir(source);os.environ['SKIP_INTEGRATION']='0'
    import pytest
    records=[]
    class Collector:
        active=None
        def pytest_runtest_setup(self,item):self.active=item.nodeid
        def pytest_runtest_teardown(self,item):self.active=None
        def profile(self,frame,event,arg):
            if event=='call' and self.active and frame.f_code.co_name in ('check_file','load_sql_fixture_pairs','load_sql_fixtures'):
                filename=Path(frame.f_code.co_filename)
                if filename.is_relative_to(source/'tests'):
                    records.append({'test':self.active,'function':frame.f_code.co_name,'file':str(filename.relative_to(source)),
                        'bindings':{k:encode(v) for k,v in frame.f_locals.items() if k!='self'},
                        'class_schema':encode(vars(type(frame.f_locals['self'])).get('schema')) if 'self' in frame.f_locals else None})
    plugin=Collector();sys.setprofile(plugin.profile)
    try:code=pytest.main(tests or ['tests/test_optimizer.py::TestOptimizer::test_pushdown_predicates','-q'],plugins=[plugin])
    finally:sys.setprofile(None)
    with gzip.open(args.output.resolve(),'wt') as f:json.dump({'source_pin':PINNED_COMMIT,'records':records,'baseline_exit_code':int(code),'labels_read':False,'complete':False,'gaps':['child-process bound values','native state','unselected tests','class inherited state'],'omission_evidence':False},f)
if __name__=='__main__':main()
