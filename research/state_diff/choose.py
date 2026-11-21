"""Argument-requiredness selection using baseline dataflow and validation states.

Only an existing literal Boolean flag may change. Keys, order, classes and all
executable code must remain identical. Unsupported edits retain the input set.
"""

import ast
import gzip
import hashlib
import json
from pathlib import Path

from blast.patches import apply_change, parse_patch
from research.observations.capsule_env import fingerprint


def boolean_edit(old, new):
    """Recognize one direct Boolean field, including validated composed maps."""
    lines = old.encode().splitlines(keepends=True)
    new_lines = new.encode().splitlines(keepends=True)
    if len(lines) != len(new_lines):
        return None
    changed = [i for i, (a, b) in enumerate(zip(lines, new_lines)) if a != b]
    if len(changed) != 1:
        return None
    position = changed[0]
    matches = []

    def walk(node, owners=()):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                walk(child, (*owners, child.name))
            elif isinstance(child, (ast.Assign, ast.AnnAssign)) and owners:
                targets = (
                    child.targets if isinstance(child, ast.Assign) else [child.target]
                )
                if (
                    len(targets) != 1
                    or not isinstance(targets[0], ast.Name)
                    or targets[0].id != "arg_types"
                    or not isinstance(child.value, ast.Dict)
                ):
                    continue
                for key, value in zip(child.value.keys, child.value.values):
                    if not (
                        isinstance(key, ast.Constant)
                        and type(key.value) is str
                        and isinstance(value, ast.Constant)
                        and type(value.value) is bool
                        and value.lineno == value.end_lineno
                        and value.lineno - 1 == position
                    ):
                        continue
                    line = lines[position]
                    edited = (
                        line[: value.col_offset]
                        + str(not value.value).encode()
                        + line[value.end_col_offset :]
                    )
                    if edited == new_lines[position]:
                        matches.append((".".join((*owners, "arg_types")), [key.value]))
            elif not isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
            ):
                walk(child, owners)

    walk(ast.parse(old))
    # Source equality is stronger than AST equality: no other byte may change.
    # The compiled graph separately proves all unpack/copy/inheritance origins.
    return matches[0] if len(matches) == 1 else None


class ArgumentContracts:
    def __init__(self, path, readers_path, index):
        self.payload = json.loads(gzip.decompress(Path(path).read_bytes()))
        self.readers = json.loads(gzip.decompress(Path(readers_path).read_bytes()))
        index_path = Path(__file__).resolve().parents[2] / "maps/source-index.json.gz"
        if (
            self.payload.get("version") != 1
            or self.payload.get("unknown_classes")
            or self.payload["environment"] != fingerprint()
            or self.payload["index_sha256"]
            != hashlib.sha256(index_path.read_bytes()).hexdigest()
            or self.payload["readers_sha256"]
            != hashlib.sha256(Path(readers_path).read_bytes()).hexdigest()
            or self.readers.get("version") != 9
            or self.readers.get("validation_order_guard") != "multiple_missing"
            or not self.readers.get("test_code_instrumented")
            or not self.readers.get("validation_observations")
            or not self.readers.get("task_attribution")
        ):
            raise ValueError("argument contract artifact mismatch")
        self.index = index
        self.passed = index.map_ids(self.readers["passed"])

    def narrow(self, text, selected):
        self.import_hazard = False
        edits = parse_patch(text)
        if len(edits) != 1:
            return selected
        edit = edits[0]
        path = edit.old_path
        info = self.index.payload["files"].get(path)
        if (
            path != edit.new_path
            or not path.startswith("sqlglot/")
            or not info
            or self.payload["source"].get(path) != info["sha256"]
        ):
            return selected
        parsed = boolean_edit(info["source"], apply_change(info["source"], edit))
        if parsed is None:
            return selected
        key, fields = parsed
        edges = self.payload["edges"].get(path + "#" + key + ":" + fields[0])
        if not edges:
            return selected
        retained = (selected - self.passed) | (self.index.unobserved & selected)
        retained.update(
            self.index.map_ids(self.index.payload["reads"].get(path, [])) & selected
        )
        consumers = self.readers["consumers"]
        for arguments, required, field in edges:
            roles = (":raw", ":unknown", ":required_missing", ":missing:" + field)
            # Validation can run while importing an application module (for
            # example, parsing a template stored in a generator class). A
            # changed result can break imports or derived globals outside the
            # argument graph. No runtime-only reader set certifies that away.
            shared = self.readers.get("shared", [])
            if arguments + ":values" in shared or any(
                required + role in shared for role in roles
            ):
                self.import_hazard = True
                return set(self.index.all)
            # Key-only reads cannot observe a Boolean change. Application import
            # reads are represented by the compiled inheritance/dict-copy edges.
            nodes = set(consumers.get(arguments + ":values", []))
            for role in roles:
                nodes.update(consumers.get(required + role, []))
            retained.update(self.index.map_ids(nodes) & selected)
            for item in (arguments, required):
                for file in self.readers.get("test_shared", {}).get(item, []):
                    retained.update(self.index.file_consumers(file) & selected)
        return retained
