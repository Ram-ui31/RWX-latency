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
from research.state_diff.eligibility import literal_assignment


def boolean_edit(old, new):
    key = literal_assignment(old, new)
    if key is None or not key.endswith(".arg_types"):
        return None

    def value(text):
        node = ast.parse(text)
        for owner in key.split(".")[:-1]:
            node = next(
                n for n in node.body if isinstance(n, ast.ClassDef) and n.name == owner
            )
        assignment = next(
            n
            for n in node.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "arg_types" for t in n.targets)
        )
        return ast.literal_eval(assignment.value), assignment.value

    (before, literal), (after, _) = value(old), value(new)
    if not (
        type(before) is dict
        and type(after) is dict
        and list(before) == list(after)
        and all(type(k) is str for k in before)
        and all(type(v) is bool for v in (*before.values(), *after.values()))
    ):
        return None
    fields = [k for k in before if before[k] != after[k]]
    if len(fields) != 1:
        return None
    node = next(
        v
        for k, v in zip(literal.keys, literal.values)
        if isinstance(k, ast.Constant) and k.value == fields[0]
    )
    if not isinstance(node, ast.Constant) or node.lineno != node.end_lineno:
        return None
    # AST equivalence alone overlooks source/line-table observers. Accept only
    # the exact Boolean token replacement, preserving every other source byte.
    lines = old.encode().splitlines(keepends=True)
    line = lines[node.lineno - 1]
    lines[node.lineno - 1] = (
        line[: node.col_offset]
        + str(after[fields[0]]).encode()
        + line[node.end_col_offset :]
    )
    return (key, fields) if b"".join(lines) == new.encode() else None


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
            or self.readers.get("version") != 8
            or not self.readers.get("test_code_instrumented")
            or not self.readers.get("validation_observations")
            or not self.readers.get("task_attribution")
        ):
            raise ValueError("argument contract artifact mismatch")
        self.index = index
        self.passed = index.map_ids(self.readers["passed"])

    def narrow(self, text, selected):
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
            # Key-only reads cannot observe a Boolean change. Application import
            # reads are represented by the compiled inheritance/dict-copy edges.
            nodes = set(consumers.get(arguments + ":values", []))
            for role in (":raw", ":unknown", ":required_missing", ":missing:" + field):
                nodes.update(consumers.get(required + role, []))
            retained.update(self.index.map_ids(nodes) & selected)
            for item in (arguments, required):
                for file in self.readers.get("test_shared", {}).get(item, []):
                    retained.update(self.index.file_consumers(file) & selected)
        return retained
