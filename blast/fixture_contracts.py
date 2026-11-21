"""Source-validated SQL fixture reader contracts, not edit-to-answer rules."""
import ast
import hashlib

VERSION = 1
EXPECTED_HELPER_FINGERPRINT = '95708947ba76e238a8558100058a92e7b1d5b6fcc7b3dfcc52c9437c3996fcea'
HELPERS = 'tests/helpers.py'
READERS = {'load_sql_fixtures': 'sql', 'load_sql_fixture_pairs': 'pairs'}


def _filter_comments(s):
    return "\n".join([line for line in s.splitlines() if line and not line.startswith("--")])


def _extract_meta(sql):
    meta = {}
    sql_lines = sql.split("\n")
    i = 0
    while sql_lines[i].startswith("#"):
        key, val = sql_lines[i].split(":", maxsplit=1)
        meta[key.lstrip("#").strip()] = val.strip()
        i += 1
    sql = "\n".join(sql_lines[i:])
    return sql, meta


def normalize(source, kind):
    filtered = _filter_comments(source)
    if kind == 'sql':
        result, lines = [], []
        for line in filtered.splitlines():
            lines.append(line)
            if not line.startswith('#'):
                result.append('\n'.join(lines))
                lines.clear()
        return result
    if kind == 'pairs':
        statements = filtered.split(';')
        result = []
        for i in range(0, len(statements) - 1, 2):
            sql, meta = _extract_meta(statements[i].strip())
            result.append((meta, sql, statements[i + 1].strip()))
        return result
    raise ValueError('Unknown reader contract')


def helpers_fingerprint(source):
    tree = ast.parse(source)
    wanted = {'_filter_comments', '_extract_meta', *READERS}
    nodes = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted}
    if set(nodes) != wanted:
        return None
    return hashlib.sha256('\n'.join(ast.dump(nodes[n], include_attributes=False) for n in sorted(nodes)).encode()).hexdigest()


def equivalent(old, new, kinds):
    if not kinds or not set(kinds).issubset({'sql', 'pairs'}):
        return False
    try:
        return all(normalize(old, kind) == normalize(new, kind) for kind in kinds)
    except (ValueError, IndexError):
        return False
