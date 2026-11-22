"""Selection from isolated per-test baseline coverage of the pinned program.

The map (maps/isolated-coverage.json.gz) was built by running every catalog test
alone: a base interpreter imported sqlglot (those lines belong to every test), a
forked child imported one test module (its lines belong to that module's tests),
and a forked grandchild ran setUpClass, the test and class cleanup. Spawned and
child interpreters were traced too and attributed to the test that started them.
So import-time execution, caches and lazy imports are attributed to every test
that needs them, not only to the first test of a shared process.

Per changed Python file (sqlglot/ or tests/, modified in place):

* noop (docstring/comment/whitespace): tests reading the file as data
* body edits: tests that executed an edited statement, a changed compound-statement
  header, the neighbours/header of an insertion, or entered an edited lambda
* import-time edits or unparseable results: every test that executed any
  top-level statement of the file, i.e. imported it

Every other file kind is returned as a sub-patch for the existing selector.
"""
import ast
import gzip
import json
import re
from pathlib import Path

from blast.patches import apply_change, parse_patch, PatchError
from engine.astdiff import classify


class IsolatedCoverage:
    def __init__(self, path, ids):
        payload = json.loads(gzip.decompress(Path(path).read_bytes()))
        if payload.get('version') != 1:
            raise ValueError('isolated coverage version mismatch')
        bad = [k for k, v in payload['status'].items() if v != 'passed' and not v.startswith('skipped')]
        self.untrusted = set(bad) | set(payload['missing'])
        self.masks = [int(h, 16) for h in payload['masks']]
        self.lines = {f: {l: m for l, m in pairs} for f, pairs in payload['lines'].items()}
        self.calls = {f: {l: m for l, m in pairs} for f, pairs in payload['calls'].items()}
        self.map_ids = payload['ids']
        # Map positions in the coverage catalog to runtime test numbers by id.
        self.runtime = [ids.get(i) for i in self.map_ids]
        self.unknown_runtime = {n for i, n in ids.items() if i not in set(self.map_ids)}
        self.untrusted_runtime = {ids[i] for i in self.untrusted if i in ids}
        self.covered_runtime = set(n for n in self.runtime if n is not None)

    def numbers(self, mask):
        out = set()
        i = 0
        while mask:
            if mask & 1:
                n = self.runtime[i]
                if n is not None:
                    out.add(n)
            mask >>= 1
            i += 1
        return out

    def line_mask(self, path, spans):
        table = self.lines.get(path, {})
        m = 0
        for a, b in spans:
            for line in range(a, b + 1):
                k = table.get(line)
                if k is not None:
                    m |= self.masks[k]
        return m

    def call_mask(self, path, firsts):
        table = self.calls.get(path, {})
        m = 0
        for line in firsts:
            k = table.get(line)
            if k is not None:
                m |= self.masks[k]
        return m

    def importers(self, path, old):
        tree = ast.parse(old.encode('utf-8'))
        spans = []
        for s in tree.body:
            spans.append((s.lineno, s.lineno))
            for d in getattr(s, 'decorator_list', []) or []:
                spans.append((d.lineno, d.lineno))
        return self.line_mask(path, spans)


def split_blocks(text):
    changes = parse_patch(text)
    blocks = [b for b in re.split(r'(?m)(?=^diff --git )', text) if b.strip()]
    if len(blocks) != len(changes) or len({c.old_path for c in changes}) != len(changes):
        return None
    return list(zip(changes, blocks))


def select(cov, source, text, readers, defer_values=True, refine=None):
    """Return (selected runtime numbers, remaining sub-patch text, notes) or None."""
    source = Path(source)
    try:
        pairs = split_blocks(text)
    except (PatchError, ValueError):
        return None
    if pairs is None:
        return None
    selected, rest, notes = set(), [], []
    semantic = 0
    for change, block in pairs:
        path = change.old_path
        if not (path and path == change.new_path and path.endswith('.py') and not change.binary):
            semantic += 1
            continue
        try:
            old = (source / path).read_text(encoding='utf-8')
            if classify(old, apply_change(old, change))[0] != 'noop':
                semantic += 1
        except Exception:
            semantic += 1
    for change, block in pairs:
        path = change.old_path
        eligible = (path and path == change.new_path and not change.binary and change.hunks
                    and path.endswith('.py')
                    and (path.startswith('sqlglot/') or (path.startswith('tests/') and not path.startswith('tests/fixtures/'))))
        if not eligible:
            rest.append(block if block.endswith('\n') else block + '\n')
            continue
        try:
            old = (source / path).read_text(encoding='utf-8')
            new = apply_change(old, change)
        except (OSError, UnicodeError, PatchError, ValueError):
            rest.append(block if block.endswith('\n') else block + '\n')
            continue
        extra = readers(path)
        try:
            kind, spans, lambdas = classify(old, new)
        except (SyntaxError, ValueError, RecursionError):
            kind, spans, lambdas = 'syntax', [], []
        if kind == 'value' and defer_values:
            # Same-target value assignments keep the receiver/key-sensitive selector:
            # isolated importers were measured to cost more than its residual misses.
            rest.append(block if block.endswith('\n') else block + '\n')
            notes.append(f'{path}:value-deferred')
            continue
        if kind == 'noop':
            mask = 0
        elif kind == 'body':
            mask = cov.line_mask(path, spans) | cov.call_mask(path, lambdas)
            if refine is not None and semantic == 1:
                found = None
                try:
                    found = refine(block)
                except Exception:
                    found = None
                if found is not None:
                    safe, guard = found
                    file_sel = cov.numbers(mask)
                    selected |= (file_sel - safe) | (guard & file_sel) | (guard - cov.covered_runtime) | extra
                    notes.append(f'{path}:body-operands')
                    continue
        else:
            mask = cov.importers(path, old)
        selected |= cov.numbers(mask) | extra
        notes.append(f'{path}:{kind}')
    # Tests without a complete isolated baseline record are never omitted here.
    if notes:
        selected |= cov.untrusted_runtime | cov.unknown_runtime
    return selected, ''.join(rest), notes
