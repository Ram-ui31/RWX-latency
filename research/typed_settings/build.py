"""Record baseline settings dependencies, retaining shared initialization consumers."""

import argparse, subprocess, sys, os, tempfile, json, gzip, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from engine.source_origin import verify


def main():
    p = argparse.ArgumentParser()
    for k in ("source", "catalog", "output"):
        p.add_argument("--" + k, type=Path, required=True)
    a = p.parse_args()
    verify(a.source)
    source = a.source.resolve()
    here = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="rwx-typed-") as tmp:
        env = dict(
            os.environ,
            RWX_TYPED_OUT=tmp,
            RWX_TYPED_SOURCE=str(source),
            SKIP_INTEGRATION="0",
            PYTHON_CPU_COUNT="2",
            PYTHONDONTWRITEBYTECODE="1",
            PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
            PYTHONPATH=str(here) + os.pathsep + str(source),
            PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"],
        )
        tests = json.loads(a.catalog.read_text())["tests"]
        r = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-p",
                "plugin",
                "-p",
                "pytest_timeout",
                "-p",
                "no:cacheprovider",
                "-q",
                "--assert=plain",
                *[t["id"] for t in tests],
            ],
            cwd=source,
            env=env,
            timeout=300,
        )
        if r.returncode:
            raise ValueError("typed baseline did not pass")
        reports = json.loads(Path(tmp, "reports.json").read_text())
        passed = {
            n
            for n, rs in reports.items()
            if all(v == "passed" for _, v in rs)
            and {"setup", "call", "teardown"} <= {w for w, _ in rs}
        }
        consumers = {}
        test_shared = {}
        shared = set()
        for marker in Path(tmp).glob("start-*.json"):
            if not Path(tmp, marker.name.removeprefix("start-")).exists():
                owner = json.loads(marker.read_text())
                if owner:
                    passed.discard(owner)
                else:
                    passed.clear()
        for file in Path(tmp).glob("*.json"):
            if file.name == "reports.json" or file.name.startswith("start-"):
                continue
            for node, keys in json.loads(file.read_text()).items():
                if not node:
                    shared.update(keys)
                elif node.startswith("!sharedtest|"):
                    for key in keys:
                        test_shared.setdefault(key, set()).add(node.split("|", 1)[1])
                elif node in passed:
                    for k in keys:
                        consumers.setdefault(k, set()).add(node)
        from research.observations.capsule_env import fingerprint

        result = dict(
            version=8,
            validation_observations=True,
            test_shared={k: sorted(v) for k,v in test_shared.items()},
            test_code_instrumented=True,
            task_attribution=True,
            environment=fingerprint(),
            passed=sorted(passed),
            shared=sorted(shared),
            consumers={k: sorted(v) for k, v in consumers.items()},
            source={
                p.relative_to(source)
                .as_posix(): hashlib.sha256(p.read_bytes())
                .hexdigest()
                for p in (source / "sqlglot").rglob("*.py")
            },
        )
        a.output.write_bytes(gzip.compress(json.dumps(result).encode(), mtime=0))
        print("typed keys", len(consumers), "shared", len(shared), flush=True)


if __name__ == "__main__":
    main()
