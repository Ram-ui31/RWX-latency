"""Read ordinary unified git diffs without executing or applying patch code."""
from dataclasses import dataclass, field
import re


class PatchError(ValueError):
    pass


@dataclass
class Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list = field(default_factory=list)


@dataclass
class Change:
    old_path: str = ''
    new_path: str = ''
    hunks: list = field(default_factory=list)
    binary: bool = False

    def positions(self):
        """Old-source changed lines and insertion anchors (next old line)."""
        removed, inserted = set(), set()
        for h in self.hunks:
            cursor = h.old_start
            block_anchor = None
            for line in h.lines:
                if line.startswith(('-', '+')) and block_anchor is None:
                    block_anchor = cursor
                if line.startswith('-'):
                    removed.add(cursor); cursor += 1
                elif line.startswith('+'):
                    inserted.add(block_anchor)
                elif line.startswith(' '):
                    cursor += 1
                    block_anchor = None
        return removed, inserted

    def coordinates(self):
        """Actual changed old/new lines, distinct from old insertion anchors."""
        old_changed, new_changed = set(), set()
        for h in self.hunks:
            old, new = h.old_start, h.new_start
            for line in h.lines:
                if line.startswith('-'):
                    old_changed.add(old); old += 1
                elif line.startswith('+'):
                    new_changed.add(new); new += 1
                elif line.startswith(' '):
                    old += 1; new += 1
        return old_changed, new_changed


def clean_path(value):
    value = value.split('\t', 1)[0]
    if value == '/dev/null':
        return ''
    # Git's C-quoted path dialect is deliberately not guessed.
    if value.startswith('"') or '\\' in value or value.startswith('/'):
        raise PatchError('Unsupported patch path encoding')
    if value.startswith(('a/', 'b/')):
        value = value[2:]
    if not value or any(p in ('', '.', '..') for p in value.split('/')):
        raise PatchError('Invalid relative patch path')
    return value


def parse_patch(text):
    changes = []
    change = None
    hunk = None
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('diff --git '):
            change = Change(); changes.append(change); hunk = None
        elif line.startswith('--- ') and hunk is None:
            if change is None:
                change = Change(); changes.append(change)
            change.old_path = clean_path(line[4:].rstrip('\n'))
        elif line.startswith('+++ ') and hunk is None:
            if change is None: raise PatchError('Missing file header')
            change.new_path = clean_path(line[4:].rstrip('\n'))
        elif line.startswith('@@ '):
            if change is None: raise PatchError('Hunk without file')
            match = re.match(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            if not match: raise PatchError('Malformed hunk header')
            a, b, c, d = match.groups()
            hunk = Hunk(int(a), int(b) if b is not None else 1, int(c), int(d) if d is not None else 1)
            change.hunks.append(hunk)
            old_used = new_used = 0
            i += 1
            while i < len(lines) and (old_used < hunk.old_count or new_used < hunk.new_count):
                body = lines[i]
                if body.startswith('\\ No newline'):
                    if not hunk.lines: raise PatchError('Stray newline marker')
                    hunk.lines[-1] = hunk.lines[-1].rstrip('\n')
                    i += 1; continue
                if not body or body[0] not in ' +-': raise PatchError('Malformed hunk body')
                hunk.lines.append(body)
                old_used += body[0] in ' -'
                new_used += body[0] in ' +'
                if old_used > hunk.old_count or new_used > hunk.new_count:
                    raise PatchError('Hunk counts exceeded')
                i += 1
            if (old_used, new_used) != (hunk.old_count, hunk.new_count):
                raise PatchError('Incomplete hunk')
            if i < len(lines) and lines[i].startswith('\\ No newline'):
                if not hunk.lines: raise PatchError('Stray newline marker')
                hunk.lines[-1] = hunk.lines[-1].rstrip('\n'); i += 1
            hunk = None
            continue
        elif line.startswith(('GIT binary patch', 'Binary files ')):
            if change is None: raise PatchError('Binary patch without file')
            change.binary = True
        i += 1
    if not changes:
        raise PatchError('No diff found')
    for c in changes:
        if not c.old_path and not c.new_path:
            # Mode-only/rename-only changes use a conservative all-tests fallback.
            c.binary = True
    return changes


def apply_change(source, change):
    """Reconstruct the changed text only for static AST analysis. Never execute it."""
    old = source.splitlines(keepends=True)
    out, cursor = [], 0
    for h in change.hunks:
        start = h.old_start - 1 if h.old_count else h.old_start
        if start < cursor or start > len(old): raise PatchError('Overlapping/out-of-range hunk')
        out.extend(old[cursor:start]); cursor = start
        expected_new_start = h.new_start - 1 if h.new_count else h.new_start
        if expected_new_start != len(out):
            raise PatchError('New-file hunk coordinates do not match reconstruction')
        for line in h.lines:
            prefix, value = line[0], line[1:]
            if prefix in ' -':
                if cursor >= len(old) or old[cursor].rstrip('\n') != value.rstrip('\n'):
                    raise PatchError('Patch does not match pinned source')
                if prefix == ' ': out.append(old[cursor])
                cursor += 1
            elif prefix == '+':
                out.append(value)
    out.extend(old[cursor:])
    return ''.join(out)
