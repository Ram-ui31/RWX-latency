"""Conservative source-derived serialization edges across process boundaries."""
import ast

def consumers(payload,tests):
    process_files=set(); serializers=set()
    for path,info in payload['files'].items():
        tree=ast.parse(info['source'])
        names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
        names|={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
        if path.startswith('tests/') and names & {'ProcessPoolExecutor','Process','Pool','get_context'}:process_files.add(path)
        if path.startswith('sqlglot/'):
            for fn in ast.walk(tree):
                if isinstance(fn,ast.FunctionDef) and fn.name in {'__reduce__','__reduce_ex__','__getstate__','__setstate__'}:
                    serializers.add(path)
                    for node in ast.walk(fn):
                        if isinstance(node,ast.ImportFrom) and node.module and node.module.startswith('sqlglot'):
                            candidate=node.module.replace('.','/')+'.py'
                            if candidate in payload['files']:serializers.add(candidate)
    ids=sorted(t['number'] for t in tests if t['file'] in process_files)
    return {path:ids for path in sorted(serializers)}
