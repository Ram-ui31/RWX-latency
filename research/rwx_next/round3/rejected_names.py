"""Additive name-dependency guard for initialization edits.

Inspired by name/element propagation, not a reproduction of NameRTS. Names are
conservatively conflated; this graph can ADD tests but never justify an omission.
"""
import ast
from collections import defaultdict
from blast.patches import parse_patch,apply_change

def references(node):
    if node is None:return set()
    result={n.id for n in ast.walk(node) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load)}
    result.update(n.attr for n in ast.walk(node) if isinstance(n,ast.Attribute))
    # Reflective literal accesses remain visible; nonliteral reflection is unknown.
    for n in ast.walk(node):
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in {'getattr','hasattr','setattr'}:
            if len(n.args)>1 and isinstance(n.args[1],ast.Constant) and isinstance(n.args[1].value,str):result.add(n.args[1].value)
    return result

def bindings(tree):
    result={}
    def walk(body,prefix=''):
        for node in body:
            if isinstance(node,ast.ClassDef):
                result[prefix+node.name]=ast.dump(ast.ClassDef(name=node.name,bases=node.bases,keywords=node.keywords,body=[],decorator_list=node.decorator_list),include_attributes=False)
                walk(node.body,prefix+node.name+'.')
            elif isinstance(node,(ast.Assign,ast.AnnAssign,ast.AugAssign)):
                targets=node.targets if isinstance(node,ast.Assign) else [node.target]
                for target in targets:
                    for name in ast.walk(target):
                        if isinstance(name,ast.Name):result[prefix+name.id]=ast.dump(node,include_attributes=False)
    walk(tree.body)
    return result

class NameGuard:
    def __init__(self,payload,tests):
        self.payload=payload;self.users=defaultdict(set);self.roots={}
        for path,info in payload['files'].items():
            tree=ast.parse(info['source'])
            for node in ast.walk(tree):
                if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    for ref in references(node):self.users[ref].add(node.name)
                elif isinstance(node,(ast.Assign,ast.AnnAssign)):
                    targets=node.targets if isinstance(node,ast.Assign) else [node.target]
                    for target in targets:
                        for name in ast.walk(target):
                            if isinstance(name,ast.Name):
                                for ref in references(node.value):self.users[ref].add(name.id)
            if path.startswith('tests/'):
                for t in tests:
                    if t['file']!=path:continue
                    method=t['id'].split('::')[-1].split('[')[0]
                    candidates=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==method]
                    self.roots[t['number']]=set().union(*(references(n) for n in candidates)) if candidates else set()
    def select(self,text):
        changed=set()
        for edit in parse_patch(text):
            path=edit.old_path
            if path not in self.payload['files'] or not path.endswith('.py'):continue
            old=self.payload['files'][path]['source'];new=apply_change(old,edit)
            a,b=bindings(ast.parse(old)),bindings(ast.parse(new))
            for name in set(a)|set(b):
                if a.get(name)!=b.get(name):changed.add(name.rsplit('.',1)[-1])
        queue=list(changed)
        while queue:
            name=queue.pop()
            for user in self.users.get(name,()):
                if user not in changed:changed.add(user);queue.append(user)
        return {n for n,refs in self.roots.items() if refs&changed}
