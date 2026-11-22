#!/usr/bin/env python3
"""Differential check for tests/test_parser.py::TestParser::test_max_nodes.

The test parses fixed SQL: three small statements, a 500-column select, a
periodic 10,000-column query of 100-deep equality chains with node limits of
1,000,000 and 50,000, and a 100-column query with a limit of 5. Almost all of its
28.8 recorded seconds are the 1,000,000-node parse of the periodic query.

``check`` runs every cheap assertion of the test exactly (including the 50,000-node
parse), and compares with the pinned baseline: the canonical trees of the small
statements and of a 20-column prefix of the periodic query, and the full error
messages of the limited parses (on a 700-column prefix, which reaches the 50,000
node limit at the same position with the same context). The 1,000,000-node parse
runs the same per-column code path, so identical results there leave the two big
assertions unchanged. Tokenizer edits that only act on very long input are the
residual risk.
"""
import json
import sys

sys.setrecursionlimit(50000)


def canon(node):
    from enum import Enum
    if node is None or isinstance(node, (str, int, float, bool)):
        return node
    if isinstance(node, Enum):
        return ['E', type(node).__qualname__, canon(node.value)]
    if isinstance(node, (list, tuple)):
        return ['L', [canon(x) for x in node]]
    if hasattr(node, 'args') and isinstance(getattr(node, 'args', None), dict):
        typ = getattr(node, '_type', None)
        return ['X', type(node).__module__ + '.' + type(node).__qualname__,
                [[k, canon(v)] for k, v in node.args.items()],
                canon(getattr(node, 'comments', None)), canon(getattr(node, '_meta', None)),
                canon(typ) if typ is not node else 'self']
    return ['O', type(node).__qualname__, repr(node)]


def observe():
    import hashlib
    from sqlglot import exp, parse_one
    from sqlglot.errors import ParseError

    def digest(v):
        return hashlib.sha256(json.dumps(v, sort_keys=True).encode()).hexdigest()

    def tree(sql, **kw):
        e = parse_one(sql, **kw)
        return [type(e).__name__, isinstance(e, exp.Select), digest(canon(e))]

    def error(sql, **kw):
        try:
            parse_one(sql, **kw)
        except ParseError as ex:
            return ['ParseError', str(ex)]
        return ['no error']

    out = {}
    out['select1'] = tree('SELECT 1', max_nodes=1_000_000)
    cols = [f'col{i}' for i in range(500)]
    out['wide'] = tree(f"SELECT {','.join(cols)} FROM t", max_nodes=1_000_000)
    expr = 'x' + '=x' * 100
    # The 50,000-node error is raised inside the first ~500 columns; a 700-column
    # prefix of the same periodic query yields the same position and context.
    big = f"SELECT {','.join([expr for _ in range(700)])}"
    out['limit50k'] = error(big, max_nodes=50_000)
    prefix = f"SELECT {','.join([expr for _ in range(20)])}"
    out['prefix'] = tree(prefix)
    out['prefix_limit'] = tree(prefix, max_nodes=1_000_000)
    out['limit5'] = error('SELECT ' + ','.join(f'x={i}' for i in range(100)), max_nodes=5)
    out['after'] = tree('SELECT 1, 2, 3')
    # The assertions of the original test, on the observed values.
    ok = (out['select1'][1] and out['wide'][1] and out['after'][1]
          and out['limit50k'][0] == 'ParseError' and '(50000)' in out['limit50k'][1]
          and out['limit5'][0] == 'ParseError')
    out['assertions'] = bool(ok)
    return out


def main():
    mode, tree, baseline = sys.argv[1:4]
    sys.path.insert(0, tree)
    try:
        got = observe()
    except Exception as ex:  # noqa: BLE001
        print(json.dumps({'status': 'error', 'error': type(ex).__name__}))
        return
    if mode == 'build':
        if not got['assertions'] or 'Maximum number of AST nodes' not in got['limit50k'][1]:
            raise SystemExit('baseline max_nodes observation failed')
        with open(baseline, 'w') as fh:
            json.dump(got, fh)
        print(json.dumps({'status': 'built'}))
        return
    with open(baseline) as fh:
        base = json.load(fh)
    print(json.dumps({'status': 'equal' if got == base else 'differs'}))


if __name__ == '__main__':
    main()
