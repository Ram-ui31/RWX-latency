"""Record immutable facts about baseline operands. Never call user-defined equality."""
import ast
import builtins
import enum
import importlib.machinery
import operator
import os
from pathlib import Path

# Maps site -> observed bit mask, partitioned by whole pytest node.
values = {}
active = None
OBSERVED_SAME = 1
OBSERVED_DISTINCT_EQUAL = 2
OBSERVED_UNEQUAL = 4
UNKNOWN = 8


def relation(left, right):
    identical = left is right
    a, b = type(left), type(right)
    if a is b and type(a) is type and a in (str, bytes, int, bool, type(None)):
        equal = left == right
    elif type(a) is enum.EnumType and a is b and a.__eq__ is str.__eq__:
        equal = str.__eq__(left, right)
    elif (type(a) is type and type(b) is type
          and (a is type(None) or a.__eq__ is object.__eq__)
          and (b is type(None) or b.__eq__ is object.__eq__)):
        equal = identical
    else:
        return UNKNOWN
    if not equal:
        return OBSERVED_UNEQUAL if not identical else UNKNOWN
    return OBSERVED_SAME if identical else OBSERVED_DISTINCT_EQUAL


def observe(site, left, right, negated):
    node = active or os.environ.get('RWX_OBSERVATION_NODE', '')
    bucket = values.setdefault(node, {})
    bucket[site] = bucket.get(site, 0) | relation(left, right)
    return (left is not right) if negated else (left is right)


ORDER = {'Lt': operator.lt, 'LtE': operator.le, 'Gt': operator.gt, 'GtE': operator.ge}


def observe_order(site, left, right, op):
    # Exact builtins only. Never call a custom comparison for profiling.
    kind = type(left)
    safe = (kind is type(right) and
            (kind is int or kind is str or
             (kind is tuple and all(type(v) is int for v in left)
              and all(type(v) is int for v in right))))
    fact = (OBSERVED_SAME if left == right else OBSERVED_UNEQUAL) if safe else UNKNOWN
    node = active or os.environ.get('RWX_OBSERVATION_NODE', '')
    bucket = values.setdefault(node, {})
    bucket[site] = bucket.get(site, 0) | fact
    return ORDER[op](left, right)


class Instrument(ast.NodeTransformer):
    def __init__(self, path):
        self.path = path

    def visit_Compare(self, node):
        self.generic_visit(node)
        if len(node.ops) != 1:
            return node
        op = type(node.ops[0]).__name__
        rhs = node.comparators[0]
        if op in ORDER and (isinstance(rhs, ast.Constant) or
                             (isinstance(rhs, ast.Tuple) and all(isinstance(v, ast.Constant) for v in rhs.elts))):
            hook, argument = '_rwx_observe_order', op
        elif isinstance(node.ops[0], (ast.Is, ast.IsNot)):
            hook, argument = '_rwx_observe_identity', isinstance(node.ops[0], ast.IsNot)
        else:
            return node
        site = f'{self.path}:{node.lineno}:{node.col_offset}'
        new = ast.Call(func=ast.Name(id=hook, ctx=ast.Load()),
                       args=[ast.Constant(site), node.left, node.comparators[0],
                             ast.Constant(argument)], keywords=[])
        return ast.copy_location(new, node)


def install(source):
    prefix = str(Path(source).resolve()) + '/'
    base = importlib.machinery.SourceFileLoader
    original = base.get_code

    loading = set()

    def get_code(loader, name):
        path = loader.path
        if not path.startswith(prefix + 'sqlglot/') or not path.endswith('.py'):
            return original(loader, name)
        loading.add(path)
        try:
            with open(path, 'rb') as handle:
                tree = ast.parse(handle.read(), filename=path)
        finally:
            loading.discard(path)
        tree = Instrument(path[len(prefix):]).visit(tree)
        return compile(ast.fix_missing_locations(tree), path, 'exec', dont_inherit=True)

    import sys
    import types
    from threading import local
    local_state = local()

    def audit(event, args):
        if event in ('os.system', 'os.posix_spawn', 'subprocess.Popen', 'os.fork'):
            node = active or os.environ.get('RWX_OBSERVATION_NODE', '')
            values.setdefault(node, {})['!external'] = 1
            return
        if event not in ('open', 'object.__getattr__', 'sys._getframe'):
            return
        if getattr(local_state, 'busy', False):
            return
        local_state.busy = True
        try:
            path = None
            code = None
            if event == 'open':
                path = args[0]
                if not isinstance(path, str) or path in loading:
                    return
                if not os.path.isabs(path):
                    path = os.path.abspath(path)
            elif event == 'sys._getframe':
                code = args[0].f_code
            else:
                obj, attr = args
                if type(obj) is types.FunctionType and attr == '__code__':
                    code = obj.__code__
                elif type(obj) is types.FrameType and attr == 'f_code':
                    code = obj.f_code
                elif type(obj) is types.TracebackType and attr == 'tb_frame':
                    code = obj.tb_frame.f_code
                elif type(obj) is types.GeneratorType and attr in ('gi_code', 'gi_frame'):
                    code = obj.gi_code
                elif type(obj) is types.CoroutineType and attr in ('cr_code', 'cr_frame'):
                    code = obj.cr_code
            if code is not None:
                path = code.co_filename
            if path and path.startswith(prefix + 'sqlglot/') and path.endswith('.py'):
                node = active or os.environ.get('RWX_OBSERVATION_NODE', '')
                key = path[len(prefix):] + ('#' + code.co_qualname if code is not None else '')
                values.setdefault(node, {})['@' + key] = 1
        finally:
            local_state.busy = False
    def resource_observer(code, offset):
        if (code.co_filename.startswith(prefix)
                and {'get_traced_memory', 'getallocatedblocks', 'get_objects', 'gettotalrefcount'}.intersection(code.co_names)):
            node = active or os.environ.get('RWX_OBSERVATION_NODE', '')
            values.setdefault(node, {})['!resource'] = 1
        return sys.monitoring.DISABLE
    mon = sys.monitoring
    mon.use_tool_id(4, 'resource observers')
    mon.register_callback(4, mon.events.PY_START, resource_observer)
    mon.set_events(4, mon.events.PY_START)
    sys.addaudithook(audit)
    builtins._rwx_observe_order = observe_order
    builtins._rwx_observe_identity = observe
    base.get_code = get_code


def task(node, function, args, kwargs):
    global active
    previous = active
    active = node
    try:
        return function(*args, **kwargs)
    finally:
        active = previous
