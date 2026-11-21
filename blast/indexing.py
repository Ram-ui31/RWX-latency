"""Static source descriptions and source/test IDs; never reads sample answers."""
import ast
import hashlib
from pathlib import Path
from functools import lru_cache

PINNED_COMMIT = 'eb11aec4be8cb2122afe713a4816662c3f0fb2fa'


@lru_cache(maxsize=16)
def parse_source(text):
    # Cached trees are read-only evidence; callers must never rewrite them.
    return ast.parse(text)


def describe_source(text):
    tree = parse_source(text)
    scopes = []
    imports = set()
    def walk(node, parents=()):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = '.'.join((*parents, child.name))
                start = min([child.lineno] + [d.lineno for d in child.decorator_list])
                scopes.append(dict(start=start, end=child.end_lineno, name=name, kind='class' if isinstance(child, ast.ClassDef) else 'function', header_end=child.body[0].lineno - 1))
                walk(child, (*parents, child.name))
            else:
                walk(child, parents)
    walk(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add('.' * node.level + (node.module or ''))
    return dict(source=text, sha256=hashlib.sha256(text.encode()).hexdigest(), scopes=scopes, imports=sorted(imports))


def repo_path(root, filename):
    try:
        return Path(filename).resolve().relative_to(root).as_posix()
    except (ValueError, OSError):
        return None
