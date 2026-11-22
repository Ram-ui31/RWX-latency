#!/usr/bin/env python3
"""Differential guard for the pinned TPC-H/TPC-DS executor tests.

test_execute_tpcds / test_execute_tpch compute, per query, parse_one(sql) in the
test process, then in a worker optimize(...) and Plan(...) followed by the Python
executor, and compare against DuckDB running transpile(sql, write="duckdb").
test_optimized_tpch compares DuckDB results of transpile(sql) and of
transpile(expected optimized sql).

``build`` (pinned source, build time) records, per query, canonical outputs of the
deterministic stages that are recomputed here (parse, DuckDB transpilation,
schema/optimizer, planner) and the set of SQLGlot lines executed by everything
else the test does (imports, class setup, pickling, table preparation, the Python
executor, result conversion).

``check`` recomputes those stage outputs in a patched tree. The selector may omit
one of these tests only when no edited line is in that "outside" set and every
recomputed output equals the baseline: every remaining computation then receives
identical inputs and runs unchanged code.
"""
import json
import os
import sys

sys.setrecursionlimit(50000)

SUITES = {
    'tpcds': dict(fixture='optimizer/tpc-ds/tpc-ds.sql', schema='TPCDS_SCHEMA', execute=True,
                  test='tests/test_executor.py::TestExecutor::test_execute_tpcds'),
    'tpch': dict(fixture='optimizer/tpc-h/tpc-h.sql', schema='TPCH_SCHEMA', execute=True,
                 test='tests/test_executor.py::TestExecutor::test_execute_tpch'),
    'opt_tpch': dict(fixture='optimizer/tpc-h/tpc-h.sql', schema='TPCH_SCHEMA', execute=False,
                     test='tests/test_executor.py::TestExecutor::test_optimized_tpch'),
}


def canon(node, seen=None):
    """Structural value of an expression tree read from raw attributes only."""
    from enum import Enum
    if node is None or isinstance(node, (str, int, float, bool)):
        return node
    if isinstance(node, Enum):
        return ['E', type(node).__qualname__, canon(node.value)]
    if isinstance(node, (list, tuple)):
        return ['L', [canon(x) for x in node]]
    if isinstance(node, dict):
        return ['D', sorted(([str(k), canon(v)] for k, v in node.items()), key=lambda kv: kv[0])]
    if hasattr(node, 'args') and isinstance(getattr(node, 'args', None), dict) and hasattr(node, 'arg_types'):
        typ = getattr(node, '_type', None)
        return ['X', type(node).__module__ + '.' + type(node).__qualname__,
                [[k, canon(v)] for k, v in node.args.items()],
                canon(getattr(node, 'comments', None)), canon(getattr(node, '_meta', None)),
                canon(typ) if typ is not node else 'self']
    return ['O', type(node).__module__ + '.' + type(node).__qualname__, repr(node)]


def canon_plan(plan):
    """Merkle signature of the plan DAG, independent of set iteration order."""
    from sqlglot.planner import Step
    memo = {}

    def val(v):
        if isinstance(v, Step):
            return ['S', sig(v)]
        if isinstance(v, (set, frozenset)):
            return ['SET', sorted(json.dumps(val(x), sort_keys=True) for x in v)]
        if isinstance(v, (list, tuple)):
            return ['L', [val(x) for x in v]]
        if isinstance(v, dict):
            return ['D', sorted((json.dumps([str(k), val(x)], sort_keys=True) for k, x in v.items()))]
        return canon(v)

    def sig(step):
        key = id(step)
        if key in memo:
            return memo[key]
        memo[key] = 'cycle'
        attrs = []
        for k, v in step.__dict__.items():
            if k == 'dependents':
                continue
            if k == 'dependencies':
                attrs.append([k, sorted(sig(d) for d in v)])
            else:
                attrs.append([k, val(v)])
        attrs.sort(key=lambda kv: kv[0])
        h = digest([type(step).__qualname__, attrs])
        memo[key] = h
        return h
    rest = sorted(([k, val(v)] for k, v in plan.__dict__.items() if k not in ('root', 'dag', '_dag')), key=lambda kv: kv[0])
    return [sig(plan.root), rest]


def digest(value):
    import hashlib
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def query_output(suite, q, schema_dict):
    from sqlglot import parse_one, transpile
    from sqlglot.optimizer import optimize
    from sqlglot.planner import Plan
    from sqlglot.schema import ensure_schema
    sql = q['sql']
    if not SUITES[suite]['execute']:
        return digest([transpile(sql, write='duckdb')[0], transpile(q['expected'], write='duckdb')[0]])
    if not q['execute']:
        return None
    expression = parse_one(sql)
    rec = [canon(expression), transpile(sql, write='duckdb')[0]]
    schema = ensure_schema(schema_dict, dialect=None)
    optimized = optimize(expression, schema, leave_tables_isolated=True, dialect=None)
    rec.append(canon(optimized))
    rec.append(canon_plan(Plan(optimized)))
    return digest(rec)


def query_lines(suite, queries, schema_dict, prefix):
    """Lines each query's recomputed stages execute, each traced alone in a fork."""
    result = []
    for q in queries:
        r, w = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(r)
            try:
                mon = sys.monitoring
                seen = set()
                tool = 5
                mon.use_tool_id(tool, 'rwx-guard-query')

                def line(code, ln):
                    f = code.co_filename
                    if f.startswith(prefix):
                        seen.add(f[len(prefix):] + ':' + str(ln))
                    return mon.DISABLE
                mon.register_callback(tool, mon.events.LINE, line)
                mon.set_events(tool, mon.events.LINE)
                query_output(suite, q, schema_dict)
                mon.set_events(tool, 0)
                data = json.dumps(sorted(seen)).encode()
            except BaseException:  # noqa
                data = b'null'
            with os.fdopen(w, 'wb') as fh:
                fh.write(data)
            os._exit(0)
        os.close(w)
        with os.fdopen(r, 'rb') as fh:
            data = fh.read()
        os.waitpid(pid, 0)
        result.append(json.loads(data))
    return result


def stage_outputs(suite, queries, schema_dict, expected=None, only=None):
    out = []
    for i, q in enumerate(queries):
        if only is not None and i not in only:
            out.append(expected[i] if expected is not None else None)
            continue
        out.append(query_output(suite, q, schema_dict))
        if expected is not None and out[-1] != expected[i]:
            return out
    return out


def _unused_stage_outputs(suite, queries, schema_dict, expected=None):
    from sqlglot import parse_one, transpile
    from sqlglot.optimizer import optimize
    from sqlglot.planner import Plan
    from sqlglot.schema import ensure_schema
    out = []
    for q in queries:
        sql = q['sql']
        if not SUITES[suite]['execute']:
            out.append(digest([transpile(sql, write='duckdb')[0], transpile(q['expected'], write='duckdb')[0]]))
            if expected is not None and out[-1] != expected[len(out) - 1]:
                return out
            continue
        if not q['execute']:
            out.append(None)
            continue
        expression = parse_one(sql)
        rec = [canon(expression), transpile(sql, write='duckdb')[0]]
        schema = ensure_schema(schema_dict, dialect=None)
        optimized = optimize(expression, schema, leave_tables_isolated=True, dialect=None)
        rec.append(canon(optimized))
        rec.append(canon_plan(Plan(optimized)))
        out.append(digest(rec))
        if expected is not None and out[-1] != expected[len(out) - 1]:
            return out
    return out


def build(root, output):
    root = os.path.abspath(root)
    prefix = root + os.sep
    os.chdir(root)
    sys.path.insert(0, root)
    os.environ['SKIP_INTEGRATION'] = '0'
    mon = sys.monitoring
    TOOL = 4
    outside = set()
    state = {'record': True}
    mon.use_tool_id(TOOL, 'rwx-guard')

    def line(code, ln):
        if not state['record']:
            return None
        f = code.co_filename
        if f.startswith(prefix):
            outside.add((f[len(prefix):], ln))
        return mon.DISABLE
    mon.register_callback(TOOL, mon.events.LINE, line)
    mon.set_events(TOOL, mon.events.LINE)

    import pickle
    import pandas as pd
    import numpy as np
    import tests.helpers as helpers
    import tests.test_executor as te
    from sqlglot import find_tables, parse_one
    from sqlglot.executor import env as _env  # noqa: F401
    from sqlglot.executor.python import PythonExecutor
    from sqlglot.executor.table import ensure_tables
    from sqlglot.optimizer import optimize
    from sqlglot.planner import Plan
    from sqlglot.schema import ensure_schema

    te.TestExecutor.setUpClass()
    result = {'suites': {}}
    per_suite_outside = {}
    for suite, cfg in SUITES.items():
        outside_before = set(outside)
        schema_dict = getattr(helpers, cfg['schema'])
        tables_all = te.TestExecutor.tpcds_tables if cfg['schema'] == 'TPCDS_SCHEMA' else te.TestExecutor.tpch_tables
        conn = te.TestExecutor.tpcds_conn if cfg['schema'] == 'TPCDS_SCHEMA' else te.TestExecutor.tpch_conn
        queries = []
        for meta, sql, expected in helpers.load_sql_fixture_pairs(cfg['fixture']):
            queries.append(dict(sql=sql, expected=expected, execute=bool(meta.get('execute'))))
        if cfg['execute']:
            for q in queries:
                if not q['execute']:
                    continue
                state['record'] = False
                expression = parse_one(q['sql'])
                state['record'] = True
                expression = pickle.loads(pickle.dumps(expression))
                tables = {t.name: tables_all[t.name] for t in find_tables(expression)}
                tables_ = ensure_tables(tables, dialect=None)
                state['record'] = False
                schema = ensure_schema(schema_dict, dialect=None)
                optimized = optimize(expression, schema, leave_tables_isolated=True, dialect=None)
                plan = Plan(optimized)
                state['record'] = True
                table = PythonExecutor(tables=tables_).execute(plan)
                table = pickle.loads(pickle.dumps(table))
                pd.DataFrame(((np.nan if c is None else c for c in r) for r in table.rows), columns=table.columns)
        # DuckDB execution of transpiled SQL needs no SQLGlot code beyond transpile (compared).
        state['record'] = False
        outputs = stage_outputs(suite, queries, schema_dict)
        state['record'] = True
        result['suites'][suite] = dict(test=cfg['test'], schema=cfg['schema'], queries=queries, outputs=outputs)
        per_suite_outside[suite] = outside_before | outside
    # Lines recorded at any point belong to every suite (shared imports/setup).
    for suite in SUITES:
        result['suites'][suite]['outside'] = sorted(outside)
    te.TestExecutor.tearDownClass()
    result['schemas'] = {cfg['schema']: getattr(helpers, cfg['schema']) for cfg in SUITES.values()}
    with open(output, 'w') as fh:
        json.dump(result, fh)
    # Per-query lines come from a cold interpreter, one fork per query.
    import subprocess
    mon.set_events(TOOL, 0)
    subprocess.run([sys.executable, '-B', os.path.abspath(__file__), 'lines', root, output], check=True)
    print('guard baseline', {s: len(v['queries']) for s, v in result['suites'].items()}, 'outside lines', len(outside), file=sys.stderr)


def check(tree, baseline, suites):
    sys.path.insert(0, os.path.abspath(tree))
    os.chdir(tree)
    data = json.load(open(baseline))
    fixtures = [a for a in suites if a.startswith('fixture=')]
    suites = [a for a in suites if not a.startswith('fixture=')]
    if fixtures:
        # Same loading as the class setup: every pair of both fixture files must load.
        sys.path.insert(1, os.environ['RWX_PINNED_ROOT'])
        from tests.helpers import _filter_comments, _extract_meta
        for item in fixtures:
            with open(item.split('=', 1)[1], encoding='utf-8') as fh:
                statements = _filter_comments(fh.read()).split(';')
            for i in range(0, len(statements), 2):
                if i + 1 < len(statements):
                    _extract_meta(statements[i].strip())
    results = {}
    edited = None
    if os.environ.get('RWX_GUARD_EDITED'):
        with open(os.environ['RWX_GUARD_EDITED']) as fh:
            wanted = set(json.load(fh))
        edited = {i for i, item in enumerate(data['line_table']) if item in wanted}
    for suite in suites:
        s = data['suites'][suite]
        schema = data['schemas'][s['schema']]
        only = None
        if edited is not None:
            only = {i for i, ls in enumerate(s['query_lines']) if ls is None or not edited.isdisjoint(ls)}
        try:
            got = stage_outputs(suite, s['queries'], schema, s['outputs'], only)
            results[suite] = 'equal' if got == s['outputs'] else 'differs'
        except Exception as ex:  # noqa: BLE001 - any failure leaves the test selected
            results[suite] = 'error:' + type(ex).__name__
    print(json.dumps(results))
    return 0


def lines_mode(root, output):
    root = os.path.abspath(root)
    os.chdir(root)
    sys.path.insert(0, root)
    import sqlglot  # noqa: F401
    data = json.load(open(output))
    table, index = [], {}
    for suite, s in data['suites'].items():
        packed = []
        for ls in query_lines(suite, s['queries'], data['schemas'][s['schema']], root + os.sep):
            if ls is None:
                packed.append(None)
                continue
            ids = []
            for item in ls:
                if item not in index:
                    index[item] = len(table); table.append(item)
                ids.append(index[item])
            packed.append(sorted(ids))
        s['query_lines'] = packed
    data['line_table'] = table
    with open(output, 'w') as fh:
        json.dump(data, fh)


if __name__ == '__main__':
    if sys.argv[1] == 'lines':
        lines_mode(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == 'build':
        build(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == 'check':
        try:
            sys.exit(check(sys.argv[2], sys.argv[3], sys.argv[4:]))
        except Exception as ex:  # unresolved
            print(json.dumps({'error': repr(ex)[:300]}))
            sys.exit(2)
