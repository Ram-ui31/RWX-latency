"""Drop Python hunks whose effect is limited to comments, whitespace or docstrings.

The pinned program and its tests never read docstrings, comments or line numbers
(checked in the pinned source: the only ``__doc__`` access copies a class's own
docstring for pdoc). Tests that read a source file as data keep their evidence
through the source index ``reads`` map, which is added back for every dropped file.

A hunk is dropped only when the docstring-normalized AST of the file with every
dropped hunk removed equals the docstring-normalized AST of the fully patched
file. Files that fail to parse, change encoding, are created, deleted, renamed or
binary are never reduced.
"""
import ast
import functools
import re
from pathlib import Path

from blast.patches import Change, Hunk, apply_change, parse_patch, PatchError
from engine.astdiff import stripped

_DOC_OWNERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def _same(a, b):
    from engine.astdiff import classify
    return classify(a, b)[0] == 'noop'


def _coding_cookie(text):
    return any(re.match(r'^[ \t\f]*#.*?coding[:=][ \t]*[-\w.]+', line)
               for line in text.splitlines()[:2])


def _apply_hunks(old, hunks):
    """Apply a subset of hunks, recomputing their new-file coordinates."""
    change = Change(hunks=_renumber(hunks))
    return apply_change(old, change)


def _renumber(hunks):
    out, offset = [], 0
    for h in hunks:
        old_pos = h.old_start - 1 if h.old_count else h.old_start
        new_pos = old_pos + offset
        new_start = new_pos + 1 if h.new_count else new_pos
        out.append(Hunk(h.old_start, h.old_count, new_start, h.new_count, list(h.lines)))
        offset += h.new_count - h.old_count
    return out


def _render(path, hunks):
    lines = [f'diff --git a/{path} b/{path}\n', f'--- a/{path}\n', f'+++ b/{path}\n']
    for h in _renumber(hunks):
        lines.append(f'@@ -{h.old_start},{h.old_count} +{h.new_start},{h.new_count} @@\n')
        for line in h.lines:
            lines.append(line if line.endswith('\n') else line + '\n\\ No newline at end of file\n')
    return ''.join(lines)


def _kept_hunks(old, change):
    """Return the hunks that matter, or None when the file cannot be reduced."""
    new = apply_change(old, change)
    if _coding_cookie(old) or _coding_cookie(new):
        return None
    if _same(old, new):
        return []
    if len(change.hunks) < 2:
        return None
    kept = []
    for h in change.hunks:
        try:
            single = _apply_hunks(old, [h])
            if not _same(old, single):
                kept.append(h)
        except (SyntaxError, ValueError, PatchError):
            kept.append(h)
    if len(kept) == len(change.hunks):
        return None
    if not _same(_apply_hunks(old, kept), new):
        return None
    return kept


def reduce_patch(source, text, index):
    """Return (reduced patch text or '', extra test numbers, dropped description)."""
    source = Path(source)
    try:
        changes = parse_patch(text)
    except (PatchError, ValueError):
        return text, set(), []
    blocks = [b for b in re.split(r'(?m)(?=^diff --git )', text) if b.strip()]
    if len(blocks) != len(changes) or len({c.old_path for c in changes}) != len(changes):
        return text, set(), []
    out, extra, dropped = [], set(), []
    for change, block in zip(changes, blocks):
        path = change.old_path
        eligible = (path and path == change.new_path and not change.binary and change.hunks
                    and path.endswith('.py') and (path.startswith('sqlglot/') or path.startswith('tests/')))
        kept = None
        if eligible:
            original = source / path
            try:
                old = original.read_text(encoding='utf-8')
                kept = _kept_hunks(old, change)
            except (OSError, UnicodeError, SyntaxError, ValueError, PatchError, RecursionError):
                kept = None
        if kept is None:
            out.append(block if block.endswith('\n') else block + '\n')
            continue
        readers = index.payload.get('reads', {}).get(path, [])
        extra.update(index.map_ids(readers))
        if kept:
            out.append(_render(path, kept))
            dropped.append(f'{path}:{len(change.hunks) - len(kept)}/{len(change.hunks)}')
        else:
            dropped.append(f'{path}:all')
    return ''.join(out), extra, dropped
