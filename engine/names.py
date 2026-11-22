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


class NameIndex:
    def __init__(self, root):
        self.mentions = defaultdict(set)  # name -> {(file, line)}
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
        for node in ast.walk(tree):
            line = getattr(node, 'lineno', None)
            if line is None:
                continue
            end = getattr(node, 'end_lineno', line) or line
            if isinstance(node, ast.Name):
                self.mentions[node.id].add((rel, line))
            elif isinstance(node, ast.Attribute):
                self.mentions[node.attr].add((rel, node.end_lineno or line))
                self.mentions[node.attr].add((rel, line))
                if node.attr in ('__dict__',):
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

    def lines_for(self, name):
        """(file, first, last) spans whose execution may observe attribute ``name``."""
        spans = [(f, l, l) for f, l in self.mentions.get(name, ())]
        for f, a, b, parts in self.dynamic:
            if _may_match(parts, name):
                spans.append((f, a, b))
        return spans
