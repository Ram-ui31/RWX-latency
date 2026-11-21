"""Baseline receiver-qualified settings reads; values and descriptors stay unchanged."""

import ast, builtins, sys, os
from pathlib import Path

reads = {}
active = None
source = None
origins = {}


def validation_roles(args, kinds, required):
    """Observe missing fields and the only possible error-order ambiguity."""
    roles = set()
    if type(args) is not dict or type(kinds) is not dict or type(required) is not set:
        return {":unknown"}
    required_missing = 0
    for argument in kinds:
        value = args.get(argument)
        kind = type(value)
        if kind not in {
            type(None),
            bool,
            int,
            float,
            str,
            bytes,
            list,
            tuple,
            dict,
            set,
            frozenset,
        }:
            mro = type.__getattribute__(kind, "__mro__")
            if list in mro or any(
                base is not object
                and (
                    "__class__" in type.__getattribute__(base, "__dict__")
                    or "__getattribute__" in type.__getattribute__(base, "__dict__")
                )
                for base in mro
            ):
                roles.add(":unknown")
        if value is None or (type(value) is list and not value):
            roles.add(":missing:" + argument)
            required_missing += argument in required
    # One unchanged error has no relative order to change. A newly added or
    # removed missing field is already retained by its :missing:<field> role.
    if required_missing > 1:
        roles.add(":required_missing")
    return roles


def record(obj, name, mode="values"):
    if type(name) is not str:
        return
    if name == "__dict__":
        cls = obj if isinstance(obj, type) else type(obj)
        for parent in type.__getattribute__(cls, "__mro__"):
            for key in type.__getattribute__(parent, "__dict__"):
                if key.isupper() or key in {"arg_types", "required_args"}:
                    record(obj, key)
        return
    if not (name.isupper() or name in {"arg_types", "required_args"}):
        return
    cls = obj if isinstance(obj, type) else type(obj)
    try:
        mro = type.__getattribute__(cls, "__mro__")
        for owner in mro:
            namespace = type.__getattribute__(owner, "__dict__")
            if name not in namespace:
                continue
            if owner not in origins:
                module = sys.modules.get(namespace.get("__module__"))
                file = getattr(module, "__file__", None)
                origins[owner] = None
                if file:
                    try:
                        path = Path(file).resolve().relative_to(source).as_posix()
                    except ValueError:
                        path = None
                    if path:
                        origins[owner] = (
                            path
                            + "#"
                            + type.__getattribute__(owner, "__qualname__")
                            + "."
                        )
            prefix = origins[owner]
            if prefix:
                node = active or os.environ.get("RWX_TYPED_NODE", "")
                reads.setdefault(node, set()).add(prefix + name)
                if not node:
                    frame = sys._getframe(1)
                    while frame is not None:
                        filename = frame.f_code.co_filename
                        if filename.startswith(str(source) + "/tests/"):
                            relative = filename[len(str(source)) + 1 :]
                            reads.setdefault("!sharedtest|" + relative, set()).add(
                                prefix + name
                            )
                            break
                        if "importlib" in filename and frame.f_code.co_name in {
                            "_find_and_load",
                            "_call_with_frames_removed",
                        }:
                            break
                        frame = frame.f_back
                if name == "arg_types":
                    frame = sys._getframe(2)
                    while frame is not None:
                        filename = frame.f_code.co_filename
                        if filename.startswith(str(source) + "/tests/"):
                            break
                        if frame.f_code.co_name == "<module>" and filename.startswith(
                            str(source) + "/sqlglot/"
                        ):
                            mode = "initialization"
                            break
                        frame = frame.f_back
                    reads[node].add(prefix + name + ":" + mode)
                if name == "required_args":
                    frame = sys._getframe(2)
                    if (
                        frame.f_code.co_name == "error_messages"
                        and frame.f_code.co_filename.endswith(
                            "/sqlglot/expressions/core.py"
                        )
                    ):
                        args = object.__getattribute__(obj, "args")
                        kinds = getattr(type(obj), "arg_types", {})
                        for role in validation_roles(args, kinds, namespace[name]):
                            reads[node].add(prefix + name + role)
                    else:
                        reads[node].add(prefix + name + ":raw")
            return
    except (AttributeError, TypeError):
        return


def attribute(obj, name, mode="values"):
    value = getattr(obj, name)
    record(obj, name, mode)
    return value


def dynamic(func, *args, **kwargs):
    value = func(*args, **kwargs)
    if func is builtins.getattr and len(args) >= 2:
        record(args[0], args[1])
    if func is builtins.vars and args:
        record(args[0], "__dict__")
    if (
        getattr(func, "__module__", None) == "inspect"
        and getattr(func, "__name__", "") in {"getmembers", "getmembers_static"}
        and args
    ):
        record(args[0], "__dict__")
    return value


class Transform(ast.NodeTransformer):
    def __init__(self):
        self.parents = []

    def visit(self, node):
        self.parents.append(node)
        try:
            return super().visit(node)
        finally:
            self.parents.pop()

    def visit_Attribute(self, node):
        self.generic_visit(node)
        mode = "values"
        parent = self.parents[-2] if len(self.parents) > 1 else None
        if node.attr == "arg_types":
            if isinstance(parent, (ast.For, ast.comprehension)) and parent.iter is node:
                mode = "keys"
            elif (
                isinstance(parent, ast.Compare)
                and node in parent.comparators
                and all(isinstance(op, (ast.In, ast.NotIn)) for op in parent.ops)
            ):
                mode = "keys"
            elif (
                isinstance(parent, ast.Call)
                and isinstance(parent.func, ast.Name)
                and parent.func.id in {"len", "tuple", "set", "list", "iter"}
            ):
                mode = "keys"
        if isinstance(node.ctx, ast.Load) and (
            node.attr.isupper()
            or node.attr in {"__dict__", "arg_types", "required_args"}
        ):
            return ast.copy_location(
                ast.Call(
                    ast.Name("_rwx_typed_attr", ast.Load()),
                    [node.value, ast.Constant(node.attr), ast.Constant(mode)],
                    [],
                ),
                node,
            )
        return node

    def visit_Call(self, node):
        self.generic_visit(node)
        if (
            isinstance(node.func, ast.Name)
            and node.func.id in ("getattr", "vars", "getmembers", "getmembers_static")
            and node.args
        ):
            return ast.copy_location(
                ast.Call(
                    ast.Name("_rwx_typed_getattr", ast.Load()),
                    [node.func, *node.args],
                    node.keywords,
                ),
                node,
            )
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in {"getmembers", "getmembers_static"}
            and node.args
        ):
            return ast.copy_location(
                ast.Call(
                    ast.Name("_rwx_typed_getattr", ast.Load()),
                    [node.func, *node.args],
                    node.keywords,
                ),
                node,
            )
        return node


def install(root):
    import importlib.machinery

    global source
    source = Path(root).resolve()
    base = importlib.machinery.SourceFileLoader
    old = base.get_code

    def get_code(loader, name):
        path = Path(loader.path)
        if (
            path.is_relative_to(source / "sqlglot")
            or path.is_relative_to(source / "tests")
        ) and path.suffix == ".py":
            tree = Transform().visit(ast.parse(path.read_bytes(), filename=str(path)))
            return compile(
                ast.fix_missing_locations(tree), str(path), "exec", dont_inherit=True
            )
        return old(loader, name)

    builtins._rwx_typed_attr = attribute
    builtins._rwx_typed_getattr = dynamic
    base.get_code = get_code


def task(node, func, args, kwargs):
    global active
    previous = active
    active = node
    try:
        return func(*args, **kwargs)
    finally:
        active = previous
