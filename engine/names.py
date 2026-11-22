"""Static name-mention index over the pinned source, for import-time value edits.

For every identifier, the source lines that mention it as a name, attribute,
keyword argument, or exact string constant. Lines that read attributes by a
computed name (getattr/hasattr/setattr/delattr with a non-constant name,
``__dict__``, ``vars``, ``dir``, ``inspect.getmembers``) are kept separately,
with the constant fragments of f-strings/concatenations when they are known.
"""
import ast
from collections import defaultdict
from pathlib import Path

_DYN_FUNCS = {'getattr', 'hasattr', 'setattr', 'delattr'}


def _fragments(node):
    """Constant pieces of a computed attribute name, or None when unknown."""
    if isinstance(node, ast.JoinedStr):
        parts = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                parts.append(v.value)
            else:
                parts.append(None)
        return parts
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _fragments(node.left), _fragments(node.right)
        if left is None or right is None:
            return None
        return left + right
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    return [None]


def _may_match(parts, name):
    """Whether a pattern of constant/unknown parts can spell ``name``."""
    if parts is None:
        return True
    import re
    rx = ''.join(re.escape(p) if p is not None else '.*' for p in parts)
    return re.fullmatch(rx, name, re.S) is not None


# Computed-name reads in the pinned source reviewed as unable to read an upper-case
# class setting: dispatch tables filtered to ``*_sql`` methods, instance/expression
# attributes, token repr, and module-level lookups (only relevant to module names).
_INSTANCE_ONLY = {
    ('sqlglot/generator.py', 79), ('sqlglot/generator.py', 87),
    ('sqlglot/optimizer/simplify.py', 1982), ('sqlglot/optimizer/simplify.py', 1984),
    ('sqlglot/expressions/core.py', 2491), ('sqlglot/expressions/core.py', 2517),
    ('sqlglot/generators/duckdb.py', 1434), ('sqlglot/tokenizer_core.py', 538),
    ('sqlglot/executor/env.py', 283), ('sqlglot/helper.py', 286),
}
_MODULE_ONLY = {
    ('sqlglot/dialects/__init__.py', 125), ('sqlglot/dialects/dialect.py', 249),
    ('sqlglot/dialects/dialect.py', 250), ('sqlglot/optimizer/__init__.py', 57),
    ('sqlglot/helper.py', 153), ('sqlglot/serde.py', 120),
}


class NameIndex:
    def __init__(self, root):
        self.mentions = defaultdict(set)  # name -> {(file, line)} reads
        self.stores = defaultdict(set)  # name -> {(file, line)} plain assignments
        self.dynamic = []  # (file, line, parts or None)
        root = Path(root)
        for base in ('sqlglot', 'tests'):
            for path in sorted((root / base).rglob('*.py')):
                rel = path.relative_to(root).as_posix()
                try:
                    tree = ast.parse(path.read_bytes())
                except SyntaxError:
                    continue
                self._scan(rel, tree)

    def _scan(self, rel, tree):
        parent = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parent[child] = node
        for node in ast.walk(tree):
            line = getattr(node, 'lineno', None)
            if line is None:
                continue
            end = getattr(node, 'end_lineno', line) or line
            if isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Store) and not isinstance(parent.get(node), ast.AugAssign):
                    self.stores[node.id].add((rel, line))
                    continue
                self.mentions[node.id].add((rel, line))
            elif isinstance(node, ast.Attribute):
                if isinstance(node.ctx, ast.Store) and not isinstance(parent.get(node), ast.AugAssign):
                    self.stores[node.attr].add((rel, line))
                    continue
                self.mentions[node.attr].add((rel, node.end_lineno or line))
                self.mentions[node.attr].add((rel, line))
                if node.attr in ('__dict__',):
                    up = parent.get(node)
                    key = None
                    if isinstance(up, ast.Attribute) and up.attr == 'get' and isinstance(parent.get(up), ast.Call):
                        call = parent.get(up)
                        if call.args and isinstance(call.args[0], ast.Constant):
                            key = call.args[0].value
                    elif isinstance(up, ast.Subscript) and isinstance(up.slice, ast.Constant):
                        key = up.slice.value
                    elif isinstance(up, ast.Compare) and isinstance(up.left, ast.Constant) \
                            and all(isinstance(o, (ast.In, ast.NotIn)) for o in up.ops):
                        key = up.left.value
                    if isinstance(key, str):
                        self.mentions[key].add((rel, line))
                    else:
                        self.dynamic.append((rel, line, end, None))
            elif isinstance(node, ast.alias):
                self.mentions[node.name.split('.')[-1]].add((rel, line))
                if node.asname:
                    self.mentions[node.asname].add((rel, line))
            elif isinstance(node, ast.keyword) and node.arg:
                self.mentions[node.arg].add((rel, line))
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.isidentifier():
                self.mentions[node.value].add((rel, line))
            elif isinstance(node, ast.Call):
                f = node.func
                fname = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
                if fname in _DYN_FUNCS and len(node.args) >= 2:
                    arg = node.args[1]
                    if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
                        self.dynamic.append((rel, line, end, _fragments(arg)))
                elif fname in ('vars', 'dir', 'getmembers'):
                    self.dynamic.append((rel, line, end, None))

    def lines_for(self, name, class_setting=False):
        """(file, first, last) spans whose execution may observe attribute ``name``.

        With ``class_setting`` (an upper-case attribute assigned in a class body),
        reviewed instance/module-only computed reads are skipped.
        """
        spans = [(f, l, l) for f, l in self.mentions.get(name, ())]
        for f, a, b, parts in self.dynamic:
            if class_setting and ((f, a) in _INSTANCE_ONLY or (f, a) in _MODULE_ONLY):
                continue
            if _may_match(parts, name):
                spans.append((f, a, b))
        return spans
