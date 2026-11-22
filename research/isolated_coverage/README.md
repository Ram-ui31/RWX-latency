# Isolated per-test coverage map

`maps/isolated-coverage.json.gz` is built from the pinned SQLGlot commit only (no patches,
no labels). Each catalog test runs alone:

1. a base interpreter imports `sqlglot` under `sys.monitoring` line/function tracing; those
   lines belong to every test;
2. a forked child imports one test module; its lines belong to that module's tests;
3. a forked grandchild runs `setUpClass`, the single test and class cleanup; spawned and
   child interpreters (process pools, `subprocess`) are traced through `site/sitecustomize.py`
   and attributed to that test.

So import-time work, caches and lazy imports are attributed to every test that needs them,
not only to the first test of a shared process. All 1,620 tests passed in isolation.

Rebuild (Linux amd64, Python 3.13, `requirements.lock`, `SKIP_INTEGRATION=0`, ~8 minutes on
2 cores):

```bash
python research/isolated_coverage/trace.py /path/to/pinned-sqlglot build-catalog.json /tmp/trace 0 2 &
python research/isolated_coverage/trace.py /path/to/pinned-sqlglot build-catalog.json /tmp/trace 1 2
python research/isolated_coverage/build_map.py /tmp/trace build-catalog.json maps/isolated-coverage.json.gz
```

`build_map.py` strips the absolute source prefix recorded by child interpreters; it assumes
the source lives at `/app/pinned-source/` as in the image.
