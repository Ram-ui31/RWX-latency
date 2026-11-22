#!/usr/bin/env python3
"""Aggregate isolated traces into a compact line/function -> tests map.

usage: build_map.py TRACE_DIR CATALOG OUT.json.gz
"""
import glob, gzip, json, os, sys
from collections import defaultdict

trace, catalog, out = sys.argv[1:4]
tests = json.load(open(catalog))['tests']
ids = [t['id'] for t in tests]
num = {t['number']: i for i, t in enumerate(tests)}
by_file = defaultdict(list)
for t in tests:
    by_file[t['id'].split('::')[0]].append(num[t['number']])

lines = defaultdict(int)   # (file, line) -> mask
calls = defaultdict(int)
status = {}
ALL = (1 << len(ids)) - 1


def add(rec, mask):
    for f, l in rec['lines']:
        lines[(f, l)] |= mask
    for f, l in rec['calls']:
        calls[(f, l)] |= mask


base = json.load(open(os.path.join(trace, 'base.json')))
add(base, ALL)
for p in glob.glob(os.path.join(trace, 'module-tests__*.json')):
    rec = json.load(open(p))
    mask = 0
    for n in rec['tests']:
        mask |= 1 << num[n]
    add(rec, mask)
missing = []
for t in tests:
    i = num[t['number']]
    p = os.path.join(trace, f"test-{t['number']}.json")
    if not os.path.exists(p):
        missing.append(t['id']); continue
    rec = json.load(open(p))
    status[t['id']] = rec['status']
    add(rec, 1 << i)
    for c in glob.glob(os.path.join(trace, 'children', str(t['number']), '*.json')):
        try:
            crec = json.load(open(c))
        except ValueError:
            status[t['id']] = 'child_unreadable'
            continue
        root = '/app/pinned-source/'
        crec['lines'] = [(f[len(root):] if f.startswith(root) else f, l) for f, l in crec['lines']]
        crec['calls'] = [(f[len(root):] if f.startswith(root) else f, l) for f, l in crec['calls']]
        add(crec, 1 << i)

masks, mindex = [], {}


def intern(m):
    if m not in mindex:
        mindex[m] = len(masks); masks.append(m)
    return mindex[m]


def pack(d):
    o = defaultdict(list)
    for (f, l), m in sorted(d.items()):
        o[f].append([l, intern(m)])
    return o


payload = dict(version=1, ids=ids, lines=pack(lines), calls=pack(calls), status=status,
               missing=missing, masks=[format(m, 'x') for m in masks])
data = json.dumps(payload, separators=(',', ':')).encode()
open(out, 'wb').write(gzip.compress(data, 9))
bad = {k: v for k, v in status.items() if v != 'passed'}
print('tests', len(ids), 'missing', len(missing), 'non-passed', len(bad), 'lines', len(lines), 'calls', len(calls),
      'masks', len(masks), 'bytes', os.path.getsize(out), file=sys.stderr)
print(json.dumps(dict(list(bad.items())[:20]), indent=1), file=sys.stderr)
