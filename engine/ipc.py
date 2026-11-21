"""Conservative process transport closure through local/imported helper calls.

Baseline source relations only. Unresolved dynamic dispatch is not proved safe.
"""
import ast
from collections import deque

def consumers(payload,tests):
    files=payload['files'];trees={p:ast.parse(i['source']) for p,i in files.items()}
    functions={};by_file={};imports={};process_files=set()
    def module_path(module):
        path=module.replace('.','/')
        return next((p for p in (path+'.py',path+'/__init__.py') if p in files),None)
    for path,tree in trees.items():
        by_file[path]={};imports[path]={}
        def walk(node,prefix=''):
            for child in ast.iter_child_nodes(node):
                if isinstance(child,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                    qual=prefix+child.name
                    if isinstance(child,(ast.FunctionDef,ast.AsyncFunctionDef)):
                        functions[path,qual]=child;by_file[path][qual]=child
                    walk(child,qual+'.')
                else:walk(child,prefix)
        walk(tree)
        for n in ast.walk(tree):
            if isinstance(n,ast.ImportFrom) and n.module:
                if n.module in ('concurrent.futures','multiprocessing') and any(a.name in {'ProcessPoolExecutor','Process','Pool','get_context'} for a in n.names):process_files.add(path)
                for a in n.names:
                    target=module_path(n.module+'.'+a.name)
                    imports[path].setdefault(a.asname or a.name,set()).add((target,None) if target else (module_path(n.module),a.name))
            elif isinstance(n,ast.Import):
                for a in n.names:
                    imports[path].setdefault(a.asname or a.name,set()).add((module_path(a.name),None))
                    if a.name.startswith(('multiprocessing','concurrent.futures')):process_files.add(path)
        names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}|{n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
        if names & {'ProcessPoolExecutor','Process','Pool','get_context'}:process_files.add(path)
    pending=deque(key for key in functions if key[1].split('.')[-1] in {'__reduce__','__reduce_ex__','__getstate__','__setstate__'} and key[0].startswith('sqlglot/'))
    seen=set();dependencies=set()
    def target(path,name):
        found=[]
        if name in by_file[path]:found.append((path,name))
        for p,q in imports[path].get(name,()):
            if p:
                dependencies.add(p)
                if q in by_file[p]:found.append((p,q))
        return found
    while pending:
        key=pending.popleft()
        if key in seen:continue
        seen.add(key);path,qual=key;dependencies.add(path);fn=functions[key]
        # Imports inside hooks are dependencies even when returned as callables.
        for n in ast.walk(fn):
            if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load):
                t=target(path,n.id)
                pending.extend(t)
            elif isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute):
                f=n.func
                if isinstance(f.value,ast.Name) and f.value.id in ('self','cls'):
                    owner=qual.rsplit('.',1)[0] if '.' in qual else ''
                    q=owner+'.'+f.attr
                    if q in by_file[path]:pending.append((path,q))
                elif isinstance(f.value,ast.Name):
                    for p,_ in imports[path].get(f.value.id,()):
                        if p:
                            dependencies.add(p)
                            if f.attr in by_file[p]:pending.append((p,f.attr))
    ids=sorted(t['number'] for t in tests if t['file'] in process_files)
    return {path:ids for path in sorted(dependencies)}
