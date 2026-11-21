"""Compile class argument-requiredness propagation from the pinned source."""

import ast
import importlib
import inspect
import json
from pathlib import Path
import sys
import hashlib
import gzip

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def compile_graph(source, inventory):
    sys.path.insert(0, str(source.resolve()))
    modules = {}
    definitions = {}
    module_literals = {}
    for path in inventory:
        if (
            not path.startswith("sqlglot/")
            or not path.endswith(".py")
            or path.endswith("/__main__.py")
        ):
            continue
        name = path.removesuffix(".py").replace("/", ".").removesuffix(".__init__")
        module = importlib.import_module(name)
        modules[name] = module
        tree = ast.parse((source / path).read_text())
        for statement in tree.body:
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                targets = (
                    statement.targets
                    if isinstance(statement, ast.Assign)
                    else [statement.target]
                )
                try:
                    literal = ast.literal_eval(statement.value)
                except (ValueError, TypeError):
                    continue
                for target in targets:
                    if isinstance(target, ast.Name) and type(literal) is dict:
                        module_literals[id(vars(module).get(target.id))] = literal

        def walk(node, owners=()):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.ClassDef):
                    key = path + "#" + ".".join((*owners, child.name))
                    definitions[key] = child
                    walk(child, (*owners, child.name))
                elif not isinstance(
                    child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
                ):
                    walk(child, owners)

        walk(tree)

    from sqlglot.expressions.core import Expr

    classes = set()

    def descendants(cls):
        if cls in classes:
            return
        classes.add(cls)
        for child in cls.__subclasses__():
            descendants(child)

    descendants(Expr)
    for module in modules.values():
        for value in vars(module).copy().values():
            if isinstance(value, type) and issubclass(value, Expr):
                classes.add(value)
    cache = {}
    visiting = set()

    def name(cls):
        module = sys.modules[cls.__module__]
        path = Path(module.__file__).resolve().relative_to(source).as_posix()
        return path + "#" + cls.__qualname__

    def resolve(node, module):
        if isinstance(node, ast.Name):
            return vars(module)[node.id]
        if isinstance(node, ast.Attribute):
            return getattr(resolve(node.value, module), node.attr)
        raise ValueError("computed class reference")

    def provenance(cls):
        if cls in cache:
            return cache[cls]
        if cls in visiting:
            raise ValueError("recursive argument definition")
        visiting.add(cls)
        try:
            if "arg_types" not in vars(cls):
                owner = next(p for p in cls.__mro__[1:] if "arg_types" in vars(p))
                result = provenance(owner).copy()
            else:
                definition = definitions[name(cls)]
                assignment = next(
                    n
                    for n in definition.body
                    if isinstance(n, (ast.Assign, ast.AnnAssign))
                    and any(
                        isinstance(t, ast.Name) and t.id == "arg_types"
                        for t in (
                            n.targets if isinstance(n, ast.Assign) else [n.target]
                        )
                    )
                )
                module = sys.modules[cls.__module__]

                def evaluate(value):
                    if isinstance(value, ast.Attribute) and value.attr == "arg_types":
                        return provenance(resolve(value.value, module)).copy()
                    if (
                        isinstance(value, ast.Call)
                        and isinstance(value.func, ast.Attribute)
                        and value.func.attr == "copy"
                        and not value.args
                        and not value.keywords
                    ):
                        return evaluate(value.func.value)
                    if isinstance(value, ast.Name):
                        actual = resolve(value, module)
                        literal = module_literals.get(id(actual))
                        if (
                            literal != actual
                            or type(literal) is not dict
                            or any(
                                type(k) is not str or type(v) is not bool
                                for k, v in literal.items()
                            )
                        ):
                            raise ValueError("nonliteral module argument map")
                        return {k: (v, None) for k, v in literal.items()}
                    if not isinstance(value, ast.Dict):
                        raise ValueError("unsupported argument definition")
                    result = {}
                    for key, item in zip(value.keys, value.values):
                        if key is None:
                            result.update(evaluate(item))
                        else:
                            field = ast.literal_eval(key)
                            flag = ast.literal_eval(item)
                            if type(field) is not str or type(flag) is not bool:
                                raise ValueError("nonboolean argument")
                            result[field] = (flag, name(cls) + ".arg_types:" + field)
                    return result

                result = evaluate(assignment.value)
            if {k: v[0] for k, v in result.items()} != cls.arg_types:
                raise ValueError("initialized argument map differs")
            cache[cls] = result
            return result
        finally:
            visiting.remove(cls)

    edges = {}
    unknown = []
    for cls in sorted(classes, key=lambda x: (x.__module__, x.__qualname__)):
        try:
            values = provenance(cls)
            expected = {k for k, (flag, _) in values.items() if flag}
            if cls.required_args != expected:
                raise ValueError("custom required-argument derivation")
            owner = next(p for p in cls.__mro__ if "arg_types" in vars(p))
            required_owner = next(p for p in cls.__mro__ if "required_args" in vars(p))
            for field, (_, origin) in values.items():
                if origin is None:
                    continue
                edge = (
                    name(owner) + ".arg_types",
                    name(required_owner) + ".required_args",
                    field,
                )
                edges.setdefault(origin, set()).add(edge)
        except (KeyError, ValueError, StopIteration, AttributeError):
            unknown.append(name(cls))
    return {
        "edges": {k: sorted(v) for k, v in edges.items()},
        "unknown_classes": unknown,
        "class_count": len(classes),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    for arg in ("source", "readers", "index", "output"):
        parser.add_argument("--" + arg, type=Path, required=True)
    parser.add_argument("--inventory", type=Path)
    args = parser.parse_args()
    from engine.source_origin import verify
    from research.observations.capsule_env import fingerprint

    verify(args.source)
    readers = json.loads(gzip.decompress(args.readers.read_bytes()))
    if readers.get("version") != 9 or readers["environment"] != fingerprint():
        raise ValueError("version-nine readers required")
    inventory = (
        json.loads(args.inventory.read_text())
        if args.inventory
        else list(json.loads(gzip.decompress(args.index.read_bytes()))["files"])
    )
    result = compile_graph(args.source.resolve(), inventory)
    if result["unknown_classes"]:
        raise ValueError(
            "unsupported argument propagation: " + str(result["unknown_classes"])
        )
    result.update(
        version=1,
        environment=fingerprint(),
        source=readers["source"],
        readers_sha256=hashlib.sha256(args.readers.read_bytes()).hexdigest(),
        index_sha256=hashlib.sha256(args.index.read_bytes()).hexdigest(),
    )
    args.output.write_bytes(
        gzip.compress(json.dumps(result, sort_keys=True).encode(), mtime=0)
    )
    print(
        "compiled",
        result["class_count"],
        "classes",
        len(result["edges"]),
        "origins",
        flush=True,
    )
