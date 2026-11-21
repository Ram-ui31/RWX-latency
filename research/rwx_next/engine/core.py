"""Exact evidence primitives. No outcome labels or mutation answer tables."""
import ast
import hashlib
import json
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def semantic_edits(before, after):
    """Preserve complete ordered trees, including signed constants and bindings."""
    result = {'before_sha256': digest(before.encode()), 'after_sha256': digest(after.encode()),
              'raw_changed': before != after}
    try:
        result.update(before_ast=ast.dump(ast.parse(before), include_attributes=False),
                      after_ast=ast.dump(ast.parse(after), include_attributes=False))
        result['ast_changed'] = result['before_ast'] != result['after_ast']
    except SyntaxError:
        result['invalid_python'] = True
    return result


def bound_value(expression, bindings):
    """Restricted exact primitive evaluator; never executes calls/attributes."""
    def evaluate(n, depth=0):
        if depth > 32: raise ValueError('depth')
        if isinstance(n, ast.Constant) and type(n.value) in (int, bool, str, type(None)):
            if len(str(n.value)) > 4096: raise ValueError('size')
            return n.value
        if isinstance(n, ast.Name) and n.id in bindings:
            v = bindings[n.id]
            if type(v) not in (int, bool, str, type(None)) or len(str(v)) > 4096: raise ValueError('type')
            return v
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.Not, ast.USub)):
            v = evaluate(n.operand, depth+1)
            if isinstance(n.op, ast.Not): return not v
            if type(v) is not int: raise ValueError('type')
            return -v
        if isinstance(n, ast.Compare):
            a = evaluate(n.left, depth+1)
            for op, other in zip(n.ops, n.comparators):
                b = evaluate(other, depth+1)
                if type(a) is not type(b): raise ValueError('mixed type')
                if isinstance(op, ast.Eq): ok = a == b
                elif isinstance(op, ast.NotEq): ok = a != b
                elif isinstance(op, ast.Lt): ok = a < b
                elif isinstance(op, ast.LtE): ok = a <= b
                elif isinstance(op, ast.Gt): ok = a > b
                elif isinstance(op, ast.GtE): ok = a >= b
                else: raise ValueError('operator')
                if not ok: return False
                a = b
            return True
        if isinstance(n, ast.BoolOp):
            value = None
            for child in n.values:
                value = evaluate(child, depth+1)
                if isinstance(n.op, ast.And) and not value: return value
                if isinstance(n.op, ast.Or) and value: return value
            return value
        raise ValueError('unsupported')
    try:
        if len(expression)>8192: raise ValueError('size')
        return {'status':'value','value':evaluate(ast.parse(expression, mode='eval').body)}
    except (ValueError, SyntaxError, TypeError, RecursionError):
        return {'status':'unknown'}


def differential_value(before, after, bindings):
    a, b = bound_value(before, bindings), bound_value(after, bindings)
    if a['status'] != 'value' or b['status'] != 'value': return {'status':'unknown'}
    return {'status':'same' if type(a['value']) is type(b['value']) and a['value']==b['value'] else 'changed',
            'before':a['value'], 'after':b['value'], 'scope':'expression_in_this_binding_only'}


def fixture_inventory(root):
    """All fixture bytes/metadata; consumer reachability must be supplied separately."""
    from blast.fixture_contracts import normalize, helpers_fingerprint
    helper = root/'tests/helpers.py'
    result = {'helper_fingerprint':helpers_fingerprint(helper.read_text()), 'fixtures':{}}
    for path in sorted((root/'tests/fixtures').rglob('*')):
        if not path.is_file() or path.is_symlink(): continue
        raw = path.read_bytes()
        item = {'sha256':digest(raw),'size':len(raw),'reader_records':{}}
        if path.suffix == '.sql':
            try:
                text = raw.decode('utf-8')
                item['source'] = text
                for kind in ('sql','pairs'):
                    try: item['reader_records'][kind] = normalize(text,kind)
                    except (ValueError,IndexError): item['reader_records'][kind] = {'status':'unknown'}
            except UnicodeError: item['encoding_unknown'] = True
        result['fixtures'][path.relative_to(root).as_posix()] = item
    return result
