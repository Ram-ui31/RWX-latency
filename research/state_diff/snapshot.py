"""Snapshot initialized class data from the pinned application in a fresh process."""
import argparse
import hashlib
import importlib
import inspect
import json
from pathlib import Path
import sys
import types


def encode(value, seen=None):
    seen = set() if seen is None else seen
    kind = type(value)
    if kind in (str, int, float, bool, type(None)):
        return [kind.__name__, value]
    if isinstance(value, type):
        return ["type", value.__module__, value.__qualname__]
    if isinstance(value, (types.FunctionType, types.BuiltinFunctionType)):
        return ["function", value.__module__, value.__qualname__]
    if isinstance(value, (classmethod, staticmethod)):
        return encode(value.__func__, seen)
    if isinstance(value, property):
        return ["property", encode(value.fget, seen)]
    if isinstance(value, types.ModuleType):
        return ["module", value.__name__]
    if id(value) in seen:
        raise ValueError("recursive data")
    seen.add(id(value))
    try:
        if kind in (list, tuple):
            return [kind.__name__, [encode(v, seen) for v in value]]
        if kind in (set, frozenset):
            return [kind.__name__, sorted((encode(v, seen) for v in value), key=repr)]
        if kind is dict:
            return ["dict", sorted([[encode(k, seen), encode(v, seen)] for k, v in value.items()], key=repr)]
        # Enums have stable primitive values and named identity.
        import enum
        if isinstance(value, enum.Enum):
            return ["enum", type(value).__module__, type(value).__qualname__, value.name, encode(value.value, seen)]
        raise ValueError("unsupported initialized value")
    finally:
        seen.remove(id(value))


def snapshot(source, inventory):
    sys.path.insert(0, str(source.resolve()))
    modules = []
    for path in inventory:
        if not path.startswith("sqlglot/") or not path.endswith(".py"):
            continue
        if path.endswith("/__main__.py"):
            continue
        name = path.removesuffix(".py").replace("/", ".").removesuffix(".__init__")
        modules.append((path, importlib.import_module(name)))
    states = {}
    opaque = []
    for path, module in modules:
        for name, value in vars(module).copy().items():
            if not isinstance(value, type) or value.__module__ != module.__name__:
                continue
            pending = [value]
            while pending:
                cls = pending.pop()
                for attr, item in vars(cls).copy().items():
                    if attr.startswith("__"):
                        continue
                    if isinstance(item, type) and item.__module__ == module.__name__ and item.__qualname__.startswith(cls.__qualname__ + "."):
                        pending.append(item)
                    key = path + "#" + cls.__qualname__ + "." + attr
                    try:
                        raw = json.dumps(encode(item), sort_keys=True).encode()
                        states[key] = hashlib.sha256(raw).hexdigest()
                    except (ValueError, TypeError, AttributeError):
                        opaque.append(key)
    return {"states": states, "opaque": sorted(opaque)}


def main():
    parser = argparse.ArgumentParser()
    for name in ("source", "inventory", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = snapshot(args.source, json.loads(args.inventory.read_text()))
    args.output.write_text(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
