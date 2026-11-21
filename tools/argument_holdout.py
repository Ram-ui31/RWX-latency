"""Generate frozen mechanism checks and label every original test independently.

Validation only. This file, generated patches and labels are never copied into
the candidate image. No selector participates in reference-test selection.
"""

import argparse
import ast
import difflib
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, "/app" if Path("/app/engine/runner.py").exists() else str(ROOT))

CASES = [
    ("array-required", "array.py", "Array", "expressions"),
    ("array-relaxed", "array.py", "ArrayAppend", "this"),
    ("json-required", "json.py", "JSONFormat", "this"),
    ("json-relaxed", "json.py", "JSONExtractScalar", "expression"),
    ("string-inheritance", "string.py", "Concat", "safe"),
    ("string-optional", "string.py", "Substring", "start"),
    ("time-noargs", "temporal.py", "CurrentDate", "this"),
    ("time-unit", "temporal.py", "DateAdd", "unit"),
    ("math-optional", "math.py", "Log", "expression"),
    ("math-relaxed", "math.py", "Atan2", "this"),
    ("core-identifier", "core.py", "Identifier", "quoted"),
    ("core-alias", "core.py", "Alias", "alias"),
]


def generate(output):
    output.mkdir(parents=True, exist_ok=True)
    (output / "commits").mkdir(exist_ok=True)
    shutil.copyfile(ROOT / "build-catalog.json", output / "tests.json")
    index = json.loads(
        gzip.decompress((ROOT / "maps/source-index.json.gz").read_bytes())
    )
    for name, filename, cls, field in CASES:
        path = "sqlglot/expressions/" + filename
        old = index["files"][path]["source"]
        owner = next(
            c
            for c in ast.parse(old).body
            if isinstance(c, ast.ClassDef) and c.name == cls
        )
        assignment = next(
            n
            for n in owner.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "arg_types" for t in n.targets)
        )
        node = next(
            v
            for k, v in zip(assignment.value.keys, assignment.value.values)
            if isinstance(k, ast.Constant) and k.value == field
        )
        if not isinstance(node, ast.Constant) or type(node.value) is not bool:
            raise ValueError("nonboolean case")
        lines = old.encode().splitlines(keepends=True)
        line = lines[node.lineno - 1]
        lines[node.lineno - 1] = (
            line[: node.col_offset]
            + str(not node.value).encode()
            + line[node.end_col_offset :]
        )
        new = b"".join(lines).decode()
        patch = (
            "diff --git a/"
            + path
            + " b/"
            + path
            + "\n"
            + "".join(
                difflib.unified_diff(
                    old.splitlines(True),
                    new.splitlines(True),
                    fromfile="a/" + path,
                    tofile="b/" + path,
                )
            )
        )
        (output / "commits" / (name + ".patch")).write_text(patch)
    (output / "manifest.json").write_text(json.dumps(CASES, indent=2))


def label_one(source, catalog, patch):
    from engine.runner import PatchedTree, PLUGIN

    tests = json.loads(catalog.read_text())["tests"]
    ids = {t["id"]: t["number"] for t in tests}
    with PatchedTree(source, patch.read_text()) as tree:
        shutil.copytree(
            source,
            tree.path,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(
                ".git", "__pycache__", "sqlglot", "tests", ".pytest_cache"
            ),
        )
        evidence = tree.path.parent / "gold.json"
        (tree.path.parent / "rwx_gold.py").write_text(PLUGIN)
        env = dict(
            os.environ,
            PYTHONPATH=str(tree.path.parent) + os.pathsep + str(tree.path),
            SKIP_INTEGRATION="0",
            PYTHONDONTWRITEBYTECODE="1",
            PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
            PYTHON_CPU_COUNT="2",
            RWX_RESULT=str(evidence),
        )
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "pytest",
                "-p",
                "rwx_gold",
                "-p",
                "pytest_timeout",
                "-p",
                "no:cacheprovider",
                "-q",
                *ids,
            ],
            cwd=tree.path,
            env=env,
            stdout=sys.stderr,
            stderr=sys.stderr,
            timeout=200,
        )
        reports = json.loads(evidence.read_text())["reports"]
        calls = {
            r["nodeid"] for r in reports if r["when"] == "call" and r["nodeid"] in ids
        }
        failed = {
            ids[r["nodeid"]]
            for r in reports
            if r["outcome"] == "failed" and r["nodeid"] in ids
        }
        if result.returncode not in (0, 1) or len(calls) != len(ids):
            raise ValueError("incomplete independent whole-suite reference")
        return dict(failing=sorted(failed), whole_tests=len(calls))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("argument-holdout"))
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--image", default="rwx-checkpoint")
    parser.add_argument("--label-one", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--catalog", type=Path)
    args = parser.parse_args()
    if args.label_one:
        print(json.dumps(label_one(args.source, args.catalog, args.label_one)))
        return
    generate(args.output)
    if args.native:
        output = args.output.resolve()
        answers = {}
        for name, *_ in CASES:
            proc = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--network",
                    "none",
                    "--cpus",
                    "2",
                    "--memory",
                    "4g",
                    "--pids-limit",
                    "256",
                    "--read-only",
                    "--tmpfs",
                    "/tmp:rw,size=64m",
                    "-v",
                    str(output) + ":/data:ro",
                    "-v",
                    str(Path(__file__).resolve()) + ":/check.py:ro",
                    "--entrypoint",
                    "python3",
                    args.image,
                    "-B",
                    "/check.py",
                    "--label-one",
                    "/data/commits/" + name + ".patch",
                    "--source",
                    "/app/pinned-source",
                    "--catalog",
                    "/app/build-catalog.json",
                ],
                capture_output=True,
                timeout=220,
                check=True,
            )
            (output / (name + ".log")).write_bytes(proc.stderr)
            answers[name] = json.loads(proc.stdout)
            (output / "answers.json").write_text(json.dumps(dict(commits=answers)))
            print(
                name,
                len(answers[name]["failing"]),
                "failing; all 1620 original tests executed",
                flush=True,
            )


if __name__ == "__main__":
    main()
