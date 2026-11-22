"""Scalar setting pruning with shared-initialization and direct-reader guards."""

import ast, gzip, json, hashlib
from pathlib import Path
from blast.patches import apply_change, parse_patch
from research.observations.capsule_env import fingerprint


def setting(old, new):
    a, b = ast.parse(old), ast.parse(new)

    def collect(tree):
        out = {}

        def walk(node, parents=()):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.ClassDef):
                    walk(child, (*parents, child.name))
                elif (
                    isinstance(child, ast.Assign)
                    and parents
                    and len(child.targets) == 1
                    and isinstance(child.targets[0], ast.Name)
                    and child.targets[0].id.isupper()
                ):
                    try:
                        value = ast.literal_eval(child.value)
                    except (ValueError, TypeError):
                        continue
                    if type(value) in (bool, int, str, type(None)):
                        out[".".join((*parents, child.targets[0].id))] = (child, value)
                elif not isinstance(
                    child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
                ):
                    walk(child, parents)

        walk(tree)
        return out

    left, right = collect(a), collect(b)
    diff = [
        k
        for k in left.keys() & right.keys()
        if ast.dump(left[k][0]) != ast.dump(right[k][0])
    ]
    if len(diff) != 1:
        return None
    key = diff[0]
    x, y = left[key], right[key]
    if type(x[1]) is not type(y[1]):
        return None
    # Require all code other than this one value to remain identical.
    x[0].value = ast.Constant(None)
    y[0].value = ast.Constant(None)
    return key if ast.dump(a) == ast.dump(b) else None


class Settings:
    def __init__(self, path, index, tests):
        self.payload = json.loads(gzip.decompress(Path(path).read_bytes()))
        if (
            self.payload.get("version") not in (2, 3, 4, 5, 6, 7, 8, 9)
            or not self.payload.get("task_attribution")
            or self.payload["environment"] != fingerprint()
        ):
            raise ValueError("typed environment mismatch")
        self.index = index
        self.passed = index.map_ids(self.payload["passed"])
        self.tests = tests
        self.test_sources = {}

    def narrow(self, text, selected):
        edits = parse_patch(text)
        if len(edits) != 1:
            return selected
        edit = edits[0]
        path = edit.old_path
        if (
            path != edit.new_path
            or not path.startswith("sqlglot/")
            or not path.endswith(".py")
        ):
            return selected
        info = self.index.payload["files"].get(path)
        if not info or self.payload["source"].get(path) != info["sha256"]:
            return selected
        old = info["source"]
        key = setting(old, apply_change(old, edit))
        if key is None:
            return selected
        origin = path + "#" + key
        if origin in self.payload["shared"]:
            return selected
        readers = self.index.map_ids(self.payload["consumers"].get(origin, []))
        readers.update(self.index.map_ids(self.index.payload["reads"].get(path, [])))
        # Attribute reflection / raw reads in test code bypass the application hook.
        name = key.rsplit(".", 1)[1]
        by_file = {}
        for test in self.tests:
            hit = by_file.get(test["file"])
            if hit is None:
                source = self.index.payload["files"].get(test["file"], {}).get("source")
                if source is None:
                    return selected
                hit = by_file[test["file"]] = name in source or any(
                    s in source for s in ("getattr", "__dict__", "getmembers", "vars(")
                )
            if hit:
                readers.add(test["number"])
        readers.update(
            t["number"]
            for t in self.tests
            if "memory" in t["id"] or "lazy_load" in t["id"]
        )
        return (selected - self.passed) | (selected & readers)
