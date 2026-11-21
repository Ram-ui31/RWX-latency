"""Collect a baseline-only test observation map from the pinned checkout."""
import argparse
import hashlib
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from engine.source_origin import verify
from engine.ipc import consumers


def build(source, catalog, output):
    source = source.resolve()
    verify(source)
    tests = json.loads(catalog.read_text())['tests']
    with tempfile.TemporaryDirectory(prefix='rwx-observations-') as tmp:
        work = Path(tmp)
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(map(str, (HERE, source))),
                   RWX_OBSERVATION_SOURCE=str(source), RWX_OBSERVATION_OUT=tmp,
                   PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTHONDONTWRITEBYTECODE='1',
                   SKIP_INTEGRATION='0', PYTHON_CPU_COUNT='2',
                   PATH=str(Path(sys.executable).parent)+os.pathsep+os.environ['PATH'])
        run = subprocess.run([sys.executable, '-m', 'pytest', '-p', 'baseline_plugin',
                              '-p', 'pytest_timeout', '-p', 'no:cacheprovider', '-q',
                              *(x['id'] for x in tests)], cwd=source, env=env)
        if run.returncode not in (0, 1):
            raise ValueError('baseline session did not finish')
        reports = json.loads((work/'reports.json').read_text())
        passed = {n for n, rows in reports.items() if
                  all(v == 'passed' for _,v in rows) and
                  {'setup', 'call', 'teardown'} <= {phase for phase,_ in rows}}
        buckets = {}
        for start in work.glob('start-*.json'):
            path = work/start.name.replace('start-', 'process-')
            if not path.exists():
                owner = json.loads(start.read_text())
                if not owner:
                    passed.clear()
                passed.discard(owner)
                continue
            for node, records in json.loads(path.read_text()).items():
                bucket = buckets.setdefault(node, {})
                for key, mask in records.items():
                    bucket[key] = bucket.get(key, 0) | mask
        if not buckets:
            raise ValueError('missing baseline evidence')
        common = buckets.get('', {})
        if '!external' in common or '!resource' in common:
            passed.clear()
        passed.difference_update(node for node, records in buckets.items() if '!external' in records or '!resource' in records)
        # Global observations veto any conflicting site evidence at a test boundary.
        sites = {}
        metadata = {}
        for node in sorted(passed):
            observations = buckets.get(node, {})
            for site, mask in observations.items():
                if site.startswith('@'):
                    metadata.setdefault(site[1:], []).append(node)
                else:
                    sites.setdefault(site, {})[node] = mask | common.get(site, 0)
        index_path = ROOT/'maps/source-index.json.gz'
        with gzip.open(index_path, 'rt') as f:
            ipc = consumers(json.load(f), tests)
        ipc_ids = {p: [tests[i]['id'] for i in numbers] for p, numbers in ipc.items()}
        from capsule_env import fingerprint
        payload = dict(version=2, ipc=ipc_ids, source_index_sha256=hashlib.sha256(index_path.read_bytes()).hexdigest(), environment=fingerprint(), passed=sorted(passed),
                       metadata=metadata, shared_metadata=[k[1:] for k in common if k.startswith('@')], sites=sites,
                       source={p.relative_to(source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in (source/'sqlglot').rglob('*.py')})
        output.write_bytes(gzip.compress(json.dumps(payload,separators=(',',':')).encode(),mtime=0))
        print(f'Captured {len(sites)} sites and {len(passed)} passing tests', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for arg in ('source', 'catalog', 'output'):
        p.add_argument('--'+arg, type=Path, required=True)
    build(**vars(p.parse_args()))
