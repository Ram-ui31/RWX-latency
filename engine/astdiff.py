"""Classify a Python source edit by where its AST differences execute.

``classify(old, new)`` returns ``(kind, sites)`` where kind is one of

* ``noop``   docstring/comment/whitespace only
* ``body``   every difference lies inside a function or lambda body that is not
             executed at definition time; sites are old-file line spans
* ``import`` some difference executes at import/definition time (module or
             class statements, decorators, defaults, annotations, signatures)

Line spans are ``(first, last)`` old-file lines whose execution evidence covers
the edit: changed statements, headers of changed compound statements, and the
neighbours/header of an insertion point.
"""
import ast
import copy
import difflib

_DEFS = (ast.FunctionDef, ast.AsyncFunctionDef)
_DOC_OWNERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def _strip(tree):
    for node in ast.walk(tree):
        if isinstance(node, _DOC_OWNERS):
            b = node.body
            if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant) \
                    and isinstance(b[0].value.value, str):
                node.body = b[1:]
    return tree


def _d(node):
    return ast.dump(node, include_attributes=False)


class Unsupported(Exception):
    pass


def _span(stmt):
    return (stmt.lineno, getattr(stmt, 'end_lineno', stmt.lineno) or stmt.lineno)


def _header_span(stmt):
    """Lines of a compound statement before its first nested block."""
    first_child = None
    for field in ('body', 'handlers', 'orelse', 'finalbody', 'cases'):
        v = getattr(stmt, field, None)
        if v:
            first_child = v[0] if first_child is None or v[0].lineno < first_child.lineno else first_child
    end = (first_child.lineno - 1) if first_child is not None else _span(stmt)[1]
    return (stmt.lineno, max(stmt.lineno, end))


_BLOCKS = {
    ast.If: ('test',), ast.While: ('test',), ast.For: ('target', 'iter', 'type_comment'),
    ast.AsyncFor: ('target', 'iter', 'type_comment'), ast.With: ('items', 'type_comment'),
    ast.AsyncWith: ('items', 'type_comment'), ast.Try: (), ast.TryStar: (),
}


def _header_equal(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, _DEFS):
        return (a.name == b.name and _d(a.args) == _d(b.args)
                and [_d(x) for x in a.decorator_list] == [_d(x) for x in b.decorator_list]
                and (_d(a.returns) if a.returns else None) == (_d(b.returns) if b.returns else None)
                and not getattr(a, 'type_params', None) and not getattr(b, 'type_params', None))
    if isinstance(a, ast.ClassDef):
        return (a.name == b.name and [_d(x) for x in a.bases] == [_d(x) for x in b.bases]
                and [_d(x) for x in a.keywords] == [_d(x) for x in b.keywords]
                and [_d(x) for x in a.decorator_list] == [_d(x) for x in b.decorator_list])
    fields = _BLOCKS.get(type(a))
    if fields is None:
        return False
    for f in fields:
        x, y = getattr(a, f, None), getattr(b, f, None)
        if isinstance(x, list):
            if [_d(i) for i in x] != [_d(i) for i in y]:
                return False
        elif isinstance(x, ast.AST) or isinstance(y, ast.AST):
            if x is None or y is None or _d(x) != _d(y):
                return False
        elif x != y:
            return False
    if isinstance(a, (ast.Try, ast.TryStar)):
        if len(a.handlers) != len(b.handlers):
            return False
        for h, k in zip(a.handlers, b.handlers):
            if (_d(h.type) if h.type else None) != (_d(k.type) if k.type else None) or h.name != k.name:
                return False
    return True


class _Diff:
    def __init__(self):
        self.sites = []
        self.import_time = False
        self.functions = []  # qualified names of functions with body edits
        self.call_sites = []  # lambda first lines whose bodies changed at definition scope
        self.structural = False  # import-time edits other than same-target value assignments
        self.value_targets = []  # (qualname, target names) of import-time value assignments

    def block(self, old, new, ctx, header=None, qual=''):
        """Compare two statement lists. ctx is 'module', 'class' or 'function'."""
        a, b = [_d(s) for s in old], [_d(s) for s in new]
        if a == b:
            return
        sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'equal':
                continue
            if tag == 'replace' and i2 - i1 == j2 - j1:
                for o, n in zip(old[i1:i2], new[j1:j2]):
                    self.pair(o, n, ctx, qual)
                continue
            if ctx != 'function':
                self.import_time = True
                self.structural = True
                continue
            # Insertions/deletions inside a function body: the removed statements
            # and the statements around the insertion point.
            for s in old[i1:i2]:
                self.sites.append(_span(s))
            if i1 > 0:
                prev = old[i1 - 1]
                self.sites.append(_header_span(prev) if type(prev) in _BLOCKS or isinstance(prev, (_DEFS, ast.ClassDef)) else _span(prev))
            if i2 < len(old):
                nxt = old[i2]
                self.sites.append(_header_span(nxt) if type(nxt) in _BLOCKS or isinstance(nxt, (_DEFS, ast.ClassDef)) else _span(nxt))
            if header is not None:
                self.sites.append(header)
            self.functions.append(qual)

    def pair(self, o, n, ctx, qual):
        if _d(o) == _d(n):
            return
        if isinstance(o, _DEFS) and _header_equal(o, n):
            q = (qual + '.' if qual else '') + o.name
            self.block(o.body, n.body, 'function', _header_span(o) if ctx == 'function' else None, q)
            return
        if isinstance(o, ast.ClassDef) and _header_equal(o, n):
            q = (qual + '.' if qual else '') + o.name
            if ctx == 'function':
                # A class defined inside a function is created at call time.
                self.block(o.body, n.body, 'function', _header_span(o), q)
            else:
                self.block(o.body, n.body, 'class', None, q)
            return
        if ctx != 'function':
            lambdas = _lambda_only(o, n)
            if lambdas is None:
                self.import_time = True
                names = _same_targets(o, n)
                if names is None:
                    self.structural = True
                else:
                    self.value_targets.append((qual, names, _span(o)))
            else:
                self.call_sites.extend(lambdas)
            return
        if type(o) in _BLOCKS and _header_equal(o, n):
            hs = _header_span(o)
            for field in ('body', 'orelse', 'finalbody'):
                self.block(getattr(o, field, []), getattr(n, field, []), 'function', hs, qual)
            for h, k in zip(getattr(o, 'handlers', []), getattr(n, 'handlers', [])):
                self.block(h.body, k.body, 'function', (h.lineno, h.lineno), qual)
            return
        if type(o) in _BLOCKS and type(o) is type(n):
            # Header changed: evidence is execution of the header.
            self.sites.append(_header_span(o))
            for field in ('body', 'orelse', 'finalbody'):
                self.block(getattr(o, field, []), getattr(n, field, []), 'function', _header_span(o), qual)
            self.functions.append(qual)
            return
        self.sites.append(_span(o))
        self.functions.append(qual)


def _same_targets(o, n):
    """Target names when two assignments bind the same simple names."""
    if type(o) is not type(n) or not isinstance(o, (ast.Assign, ast.AnnAssign)):
        return None
    ta = o.targets if isinstance(o, ast.Assign) else [o.target]
    tb = n.targets if isinstance(n, ast.Assign) else [n.target]
    if [_d(x) for x in ta] != [_d(x) for x in tb]:
        return None
    if isinstance(o, ast.AnnAssign) and (_d(o.annotation) != _d(n.annotation) or o.value is None or n.value is None):
        return None
    names = []
    for t in ta:
        if not isinstance(t, ast.Name):
            return None
        names.append(t.id)
    return names


def _mask(node):
    node = copy.deepcopy(node)
    for x in ast.walk(node):
        if isinstance(x, ast.Lambda):
            x.body = ast.Constant(value=None)
    return node


def _lambda_only(o, n):
    """Old lambda first lines when two statements differ only inside lambda bodies."""
    if _d(_mask(o)) != _d(_mask(n)):
        return None
    la = [x for x in ast.walk(o) if isinstance(x, ast.Lambda)]
    lb = [x for x in ast.walk(n) if isinstance(x, ast.Lambda)]
    if len(la) != len(lb):
        return None
    out = []
    for x, y in zip(la, lb):
        if _d(x) != _d(y):
            out.append(x.lineno)
    # Nested lambdas are reported through their outermost changed lambda as well.
    return out


def classify(old, new):
    a = _strip(ast.parse(old.encode('utf-8') if isinstance(old, str) else old))
    b = _strip(ast.parse(new.encode('utf-8') if isinstance(new, str) else new))
    if _d(a) == _d(b):
        return 'noop', [], []
    diff = _Diff()
    diff.block(a.body, b.body, 'module')
    if diff.import_time:
        if not diff.structural:
            return 'value', diff.value_targets, diff.call_sites
        return 'import', diff.sites, diff.call_sites
    return 'body', sorted(set(diff.sites)), sorted(set(diff.call_sites))
