"""Measure the actual entrypoint on public inputs under Linux runtime limits."""

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import statistics
import subprocess
import tarfile
import tempfile
import urllib.request

WRAPPER = """
import pathlib,resource,subprocess,sys
p=subprocess.run([sys.executable,'-B','/app/run_candidate.py'])
try:
 entries=dict(line.split() for line in pathlib.Path('/sys/fs/cgroup/cpu.stat').read_text().splitlines())
 cpu=int(entries['usage_usec'])/1000000
except (OSError,KeyError,ValueError):
 a=resource.getrusage(resource.RUSAGE_SELF);b=resource.getrusage(resource.RUSAGE_CHILDREN)
 cpu=a.ru_utime+a.ru_stime+b.ru_utime+b.ru_stime
print('RWX_CPU_SECONDS='+str(cpu),file=sys.stderr)
raise SystemExit(p.returncode)
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="rwx-checkpoint")
    parser.add_argument("--group-verify", choices=("0", "1"))
    parser.add_argument("--group-profile", choices=("0", "1"))
    parser.add_argument("--data", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("native-public-results.json")
    )
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="rwx-native-public-") as directory:
        root = Path(directory)
        archive = root / "sample.tar.gz"
        urllib.request.urlretrieve(
            "https://www.joinbuilders.org/buildathon/tracks/blast-radius/files/blast-radius-sample.tar.gz",
            archive,
        )
        kit = root / "official"
        kit.mkdir()
        with tarfile.open(archive) as handle:
            handle.extractall(kit, filter="data")
        data = root / "inputs"
        data.mkdir()
        inputs = args.data or kit / "sample"
        shutil.copyfile(inputs / "tests.json", data / "tests.json")
        shutil.copytree(inputs / "commits", data / "commits")
        spec = importlib.util.spec_from_file_location(
            "official_score", kit / "score.py"
        )
        scorer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scorer)
        tests = json.loads((inputs / "tests.json").read_text())["tests"]
        answers = json.loads((inputs / "answers.json").read_text())["commits"]
        results = []
        env = []
        for key, value in (
            ("RWX_GROUP_VERIFY", args.group_verify),
            ("RWX_GROUP_PROFILE", args.group_profile),
        ):
            if value is not None:
                env.extend(["-e", key + "=" + value])
        prefix = str(args.output.with_suffix("")).removesuffix("-results")
        for i in range(3):
            run = subprocess.run(
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
                    str(data) + ":/data:ro",
                    *env,
                    "--entrypoint",
                    "python3",
                    args.image,
                    "-B",
                    "-c",
                    WRAPPER,
                ],
                capture_output=True,
                timeout=175,
                check=True,
            )
            Path(f"{prefix}-{i}.jsonl").write_bytes(run.stdout)
            Path(f"{prefix}-{i}.log").write_bytes(run.stderr)
            cpu = float(
                next(
                    line.split("=", 1)[1]
                    for line in run.stderr.decode().splitlines()
                    if line.startswith("RWX_CPU_SECONDS=")
                )
            )
            score = scorer.evaluate_run(run.stdout, tests, answers)
            if not score["ok"]:
                raise ValueError(score)
            item = dict(run=i + 1, cpu_seconds=cpu, **score)
            item["total_seconds"] = score["simulated_milliseconds"] / 1000 + cpu
            results.append(item)
            print(json.dumps(item), flush=True)
        report = dict(
            results=results,
            median_total_seconds=statistics.median(r["total_seconds"] for r in results),
            timing="container cgroup CPU sampled immediately before wrapper exit",
        )
        args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
