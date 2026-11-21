"""Restricted source comparison; never executes mutated Python.

Line exclusion is supported only for equal AST structure with changed literal,
load-name, attribute or ordinary operator leaves. Structural edits use broader
function evidence. Source readers are handled separately by the selector.
"""
import ast
import marshal
from functools import lru_cache
from .indexing import parse_source


@lru_cache(maxsize=16)
def _compiled(source,filename):
    return marshal.dumps(compile(parse_source(source),filename,'exec',dont_inherit=True))


def identical_code(old, new, filename):
    return _compiled(old,filename) == _compiled(new,filename)


@lru_cache(maxsize=16)
def _scope_nodes(source):
    result={}
    def walk(node,parents=()):
        if isinstance(node,(ast.Module,ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            key=parents if isinstance(node,ast.Module) else (*parents,node.name)
            result.setdefault(key,[]).append(node)
            parents=key
        for child in ast.iter_child_nodes(node):walk(child,parents)
    walk(parse_source(source))
    return result


def docstrings_changed(old, new):
    def collect(source):
        return {key:tuple(ast.get_docstring(node,clean=False) for node in nodes)
                for key,nodes in _scope_nodes(source).items()}
    return collect(old) != collect(new)


def _header_lines(node):
    # A multiline simple statement may produce any of its line events. For
    # compound statements include the header, not the unrelated whole body.
    children = getattr(node, 'body', [])
    end = children[0].lineno - 1 if children else node.end_lineno
    return set(range(node.lineno, max(node.lineno, end) + 1))


def changed_execution_lines(old, new, scope_names=None):
    """Old-file executable regions, or None for unsupported structural edits."""
    lines = set()
    operators = (ast.operator, ast.unaryop, ast.boolop, ast.cmpop)
    def visit(a, b, region=None):
        if isinstance(a, ast.stmt):
            region = None if isinstance(a, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else _header_lines(a)
        if isinstance(a, ast.AST) and isinstance(b, ast.AST):
            if type(a) is not type(b):
                if isinstance(a, operators) and isinstance(b, type(a).__bases__[0]) and region is not None:
                    lines.update(region)
                    return True
                return False
            # New nested execution contexts/assignment expressions require a
            # more complete analysis than statement-level reachability.
            if isinstance(a, (ast.Lambda, ast.NamedExpr, ast.Yield, ast.YieldFrom, ast.Await, ast.comprehension)):
                return ast.dump(a) == ast.dump(b)
            for field in a._fields:
                x, y = getattr(a, field), getattr(b, field)
                if type(x) is type(y) and x == y:
                    continue
                if isinstance(a, ast.Constant) and field in ('value', 'kind'):
                    if region is None:
                        return False
                    lines.update(region)
                elif isinstance(a, ast.Name) and field == 'id' and isinstance(a.ctx, ast.Load):
                    if region is None:
                        return False
                    lines.update(region)
                elif isinstance(a, ast.Attribute) and field == 'attr':
                    if region is None:
                        return False
                    lines.update(region)
                elif not visit(x, y, region):
                    return False
            return True
        if isinstance(a, list) and isinstance(b, list):
            return len(a) == len(b) and all(visit(x, y, region) for x, y in zip(a, b))
        return a == b and type(a) is type(b)
    if scope_names is not None:
        before,after=_scope_nodes(old),_scope_nodes(new)
        for name in scope_names:
            key=tuple(name.split('.'))
            if len(before.get(key,[]))!=1 or len(after.get(key,[]))!=1:
                return None
            if not visit(before[key][0],after[key][0]):return None
        return lines
    return lines if visit(parse_source(old),parse_source(new)) else None
