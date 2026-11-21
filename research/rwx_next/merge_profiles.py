#!/usr/bin/env python3
"""Union source-derived traces for LOCAL diagnosis; mixed environments are explicit."""
import argparse,copy,gzip,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parent/'rwx'))
from blast.compact import pack_contexts

def unpack(p):
    ids=p['context_ids']
    def decode(x):
        if not isinstance(x,str):return x
        bits=int(x[5:],16);return [t for i,t in enumerate(ids) if bits&(1<<i)]
    for k in ('calls','lines'):
        p[k]={path:{line:decode(v) for line,v in rows.items()} for path,rows in p.get(k,{}).items()}
    for k in ('reads','module_users'):
        p[k]={path:decode(v) for path,v in p.get(k,{}).items()}
    for k in ('line_tests','line_incomplete'):p[k]=decode(p.get(k,[]))
    for f in p.get('fixtures',{}).values():f['readers']={k:decode(v) for k,v in f['readers'].items()}
    p.pop('context_encoding',None);p.pop('context_ids',None)
    return p

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--old',type=Path,required=True);ap.add_argument('--new',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    if a.output.exists():ap.error('fresh output required')
    with gzip.open(a.old,'rt') as f:p=unpack(json.load(f))
    with gzip.open(a.new,'rt') as f:q=unpack(json.load(f))
    if p['source_commit']!=q['source_commit']:raise ValueError('different baselines')
    for path,i in q['files'].items():
        if path in p['files'] and p['files'][path]['sha256']!=i['sha256']:raise ValueError('source mismatch')
    provenance=[p['environment'],q['environment']]
    for k in ('calls','lines'):
        for path,rows in q.get(k,{}).items():
            dest=p.setdefault(k,{}).setdefault(path,{})
            for line,ids in rows.items():dest[line]=sorted(set(dest.get(line,[]))|set(ids))
    for k in ('reads','module_users','shared_function_lines'):
        for path,ids in q.get(k,{}).items():p.setdefault(k,{})[path]=sorted(set(p[k].get(path,[]))|set(ids))
    for k in ('collected','line_tests','collection_reads'):
        p[k]=sorted(set(p.get(k,[]))|set(q.get(k,[])))
    for k in ('untraced','line_incomplete'):
        p[k]=sorted((set(p.get(k,[]))-set(q['collected']))|set(q.get(k,[])))
    p['outcomes'].update(q['outcomes'])
    for path,f in q.get('fixtures',{}).items():
        if path in p['fixtures']:
            old=p['fixtures'][path]
            if old['sha256']!=f['sha256']:raise ValueError('fixture mismatch')
            for kind,ids in f['readers'].items():old['readers'][kind]=sorted(set(old['readers'].get(kind,[]))|set(ids))
        else:p['fixtures'][path]=f
    p.update(partial_allowed=True,baseline_exit_code=0,mixed_environment_research=True,
             environment={'source_profiles':provenance,'canonical':False})
    pack_contexts(p)
    with gzip.open(a.output,'wt') as f:json.dump(p,f,separators=(',',':'))
if __name__=='__main__':main()
