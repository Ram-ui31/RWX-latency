"""Research selection from baseline operands and per-file first-divergence evidence."""
import ast
import gzip
import hashlib
import types
import json
from pathlib import Path
import re
import sys
from functools import lru_cache

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from blast.catalog import load_catalog
from blast.patches import apply_change, parse_patch
from blast.scheduling import optimize_schedule
from blast.selection import SourceIndex
from engine.selection import adaptive_select
from research.observations.capsule_env import fingerprint


@lru_cache(maxsize=32)
def tree_for(text):
    return ast.parse(text, type_comments=True)


def operand_site(old, new, path):
    a, b = tree_for(old), tree_for(new)
    # Match exactly one supported operator substitution across the whole module.
    sites = []
    replacements = {(ast.Is, ast.Eq): 5, (ast.Lt, ast.LtE): 4, (ast.LtE, ast.Lt): 4,
                        (ast.Gt, ast.GtE): 4, (ast.GtE, ast.Gt): 4}
    def same(x, y, owner=None):
        mask = replacements.get((type(x), type(y)))
        if mask is not None and isinstance(owner, ast.Compare):
            if len(owner.ops) != 1:
                return False
            sites.append((f'{path}:{owner.lineno}:{owner.col_offset}', mask))
            return True
        if type(x) is not type(y):
            return False
        if isinstance(x, ast.AST):
            return all(same(getattr(x, k), getattr(y, k), x) for k in x._fields)
        if isinstance(x, list):
            return len(x) == len(y) and all(same(i, j, owner) for i, j in zip(x, y))
        return x == y
    if same(a, b) and len(sites) == 1:
        return sites[0]
    return None


def plain_comment(change, old, new):
    # No inline comments, type/encoding directives, docstrings or executable tokens.
    lines = [s[1:].strip() for h in change.hunks for s in h.lines if s[0] in '+-']
    return (bool(lines) and all(re.fullmatch(r'# [A-Za-z][A-Za-z0-9 ,.-]*', s) for s in lines)
            and ast.dump(tree_for(old)) == ast.dump(tree_for(new)))


@lru_cache(maxsize=32)
def code_objects(text, path):
    result = {}
    def visit(code):
        signature = tuple(getattr(code, field) for field in (
            'co_code', 'co_names', 'co_varnames', 'co_freevars', 'co_cellvars',
            'co_argcount', 'co_posonlyargcount', 'co_kwonlyargcount', 'co_flags',
            'co_firstlineno', 'co_linetable', 'co_exceptiontable', 'co_consts'))
        result.setdefault(code.co_qualname, []).append(signature)
        for item in code.co_consts:
            if isinstance(item, types.CodeType):
                visit(item)
    visit(compile(text, path, 'exec', dont_inherit=True))
    return result


def observed_artifacts(old, new, path):
    a, b = code_objects(old, path), code_objects(new, path)
    return {path} | {path+'#'+q for q in a.keys() | b.keys() if a.get(q) != b.get(q)}


class Observations:
    def __init__(self, path, index, settings=None, tests=None, contracts=None):
        self.map = json.loads(gzip.decompress(Path(path).read_bytes()))
        if self.map['version'] != 2 or self.map['environment'] != fingerprint():
            raise ValueError('baseline observation environment mismatch')
        self.settings = None
        if settings is not None:
            from research.typed_settings.choose import Settings
            self.settings = Settings(settings, index, tests)
        self.contracts = None
        if contracts is not None:
            from research.state_diff.choose import ArgumentContracts
            self.contracts = ArgumentContracts(contracts, settings, index)
        self.index = index
        index_path = HERE.parents[1]/'maps/source-index.json.gz'
        if hashlib.sha256(index_path.read_bytes()).hexdigest() != self.map['source_index_sha256']:
            raise ValueError('source index mismatch')
        self.ipc = {p:index.map_ids(nodes) for p, nodes in self.map['ipc'].items()}
        self.passed = index.map_ids(self.map['passed'])
        self.guarded = set(index.unobserved)

    def select(self, text, comments=True, operands=True):
        changes = parse_patch(text)
        blocks = re.split(r'(?m)(?=^diff --git )', text)
        blocks = [b for b in blocks if b.strip()]
        if len(blocks) != len(changes) or len({c.old_path for c in changes}) != len(changes):
            return self.original(text, changes)
        selected = set()
        for change, block in zip(changes, blocks):
            path = change.old_path
            if path != change.new_path or change.binary or not change.hunks:
                return self.original(text, changes)
            ordinary = self.original(block, [change])
            info = self.index.payload['files'].get(path)
            if not info or not path.startswith('sqlglot/') or self.map['source'].get(path) != info['sha256']:
                selected.update(ordinary)
                continue
            old = info['source']
            new = apply_change(old, change)
            comment = comments and plain_comment(change, old, new)
            possible = any(line.startswith('-') and re.search(r'\bis\b|[<>]', line)
                           for h in change.hunks for line in h.lines)
            site = operand_site(old, new, path) if operands and len(changes) == 1 and possible and not comment else None
            if not (comment or site):
                selected.update(ordinary)
                continue
            artifacts = observed_artifacts(old, new, path)
            if not artifacts.isdisjoint(self.map['shared_metadata']):
                selected.update(ordinary)
                continue
            guard = self.guarded | self.index.map_ids(self.index.payload['reads'].get(path, []))
            for key in artifacts:
                guard.update(self.index.map_ids(self.map['metadata'].get(key, [])))
            if comment:
                ordinary = (ordinary - self.passed) | guard
            else:
                safe = {self.index.ids[node] for node, mask in self.map['sites'].get(site[0], {}).items()
                        if node in self.index.ids and mask and not (mask & ~site[1])}
                ordinary = (ordinary - safe) | guard
            selected.update(ordinary)
        if self.settings:
            selected = self.settings.narrow(text, selected)
        return self.narrow_arguments(text, selected) if self.contracts else selected

    def narrow_arguments(self, text, selected):
        narrowed = self.contracts.narrow(text, selected)
        if narrowed == selected:
            return selected
        # Typed value observations do not replace source/code/resource observers.
        # Preserve both evidence channels before authorizing an omission.
        guard = (selected - self.passed) | self.guarded
        for change in parse_patch(text):
            info = self.index.payload['files'].get(change.old_path)
            if info is None:
                return selected
            artifacts = observed_artifacts(info['source'], apply_change(info['source'], change), change.old_path)
            if not artifacts.isdisjoint(self.map['shared_metadata']):
                return selected
            for key in artifacts:
                guard.update(self.index.map_ids(self.map['metadata'].get(key, [])))
        return narrowed | (selected & guard)

    def original(self, text, changes):
        selected, _ = adaptive_select(self.index, text)
        for change in changes:
            selected.update(self.ipc.get(change.old_path, ()))
        return selected


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--map', type=Path, required=True)
    p.add_argument('--no-comments', action='store_true')
    p.add_argument('--no-operands', action='store_true')
    args = p.parse_args()
    tests, ids, durations = load_catalog(args.data/'tests.json')
    index = SourceIndex(HERE.parents[1]/'maps/source-index.json.gz', ids)
    observer = Observations(args.map, index)
    for patch in sorted((args.data/'commits').glob('*.patch')):
        try:
            selected = observer.select(patch.read_text(), not args.no_comments, not args.no_operands)
        except (ValueError, SyntaxError, OSError):
            selected = set(ids.values())
        print(json.dumps(dict(commit=patch.stem, workers=optimize_schedule(selected, durations))))


if __name__ == '__main__':
    main()
