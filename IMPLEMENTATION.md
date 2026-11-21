# Implementation checkpoint — 21 November 2026

This is a first executable implementation of the redesigned evidence pipeline.
It is not a validated replacement for the competition entry.

Implemented:

- Exact primitive expression differential evaluation, including signed values,
  input boundaries, short-circuit semantics and explicit unsupported results.
- Ordered before/after Python ASTs and raw source hashes. Comment-only changes
  remain visible. Fixture deltas preserve metadata, inputs, expected values and
  record order for both original reader contracts.
- Baseline inventory of all 63 fixture files: exact SQL records plus byte hashes
  for binary data. Reader output is not itself a proof of consumer equivalence.
- Original optimizer helper argument capture: 60 calls observed in the baseline
  pushdown-predicate test. Child/native/inherited-state gaps are recorded.
- Independent patched source trees, fresh original pytest execution, timeout
  cleanup and CPU accounting. The checkout remains untouched.
- Whole-test evidence ledger, exact marginal schedule benefit ranking, budgeted
  observation and the official JSON scheduling protocol.

The reference runner passed the actual baseline optimizer test and detected its
failure under a public fixture patch. These are noncanonical feasibility checks,
not held-out generalization results. Both runs used about 10 child CPU seconds;
that cost rules out indiscriminate whole-test replay.

## Run

From the project directory, using the research virtual environment:

```bash
fourthon/rwx/.venv/bin/python fourthon/rwx_next/build_contracts.py --source fourthon/rwx/source/sqlglot --output /tmp/new-fixture-contracts.json.gz
fourthon/rwx/.venv/bin/python fourthon/rwx_next/build_contexts.py --source fourthon/rwx/source/sqlglot --output /tmp/new-contexts.json.gz tests/test_optimizer.py::TestOptimizer::test_pushdown_predicates -q
fourthon/rwx/.venv/bin/python fourthon/rwx_next/selector.py --data-dir fourthon/rwx/sample/sample --source fourthon/rwx/source/sqlglot --index fourthon/rwx/maps/impact-index-v5.json.gz --mode hybrid --ledger /tmp/rwx-ledger.json > /tmp/rwx-predictions.jsonl
fourthon/rwx/.venv/bin/python fourthon/rwx/sample/score.py fourthon/rwx/sample/sample fourthon/rwx/sample/sample/answers.json /tmp/rwx-predictions.jsonl
fourthon/rwx/.venv/bin/python -m unittest discover -s fourthon/rwx_next -p 'test_*.py' -v
```

Add `--observe --cpu-budget 4 --action-limit 1` to collect experimental live
observations. Budgets are operational estimates; process-tree CPU can exceed an
estimate during an action. The official container meter remains authoritative.
Observation is off by default because an unpromoted adapter cannot justify a
saving and should not spend runtime CPU unnecessarily.

## Promotion boundaries

Passing-result omission is deliberately disabled. The exact Linux/amd64 image,
locked dependencies, complete baseline evidence and faithful isolation/replay
semantics have not been validated. The implementation checks environment and
baseline completeness and exposes these facts in its ledger. Local passes never
silently become competition pass certificates.

The scalar expression evaluator proves only a value relation for one supplied
binding. It is not wired to whole-test omission: doing that requires complete
binding domains and observable-state closure. Captured contexts and fixture
records are inputs to that work, not invented coverage guarantees. The executor
native-state reconstruction and automatic assertion-boundary slicing remain
unimplemented. No learned prioritization model is trained on public answers.

Default `all` mode is conservative. Explicit `hybrid` preserves the historical
retrieval policy and its assumptions; its 945.339-second sample simulation is
unchanged. This checkpoint does not establish a speed improvement. The next
performance gate is complete dependency evidence and validated fine-grained
optimizer replay, rather than enabling omissions from these local tests.

## Latest evidence-repair result

Installing DuckDB enabled a fresh optimizer/executor profile: **227 tests
passed**. `merge_profiles.py` unions source-derived dependencies with the older
profile and records both environments explicitly; this mixed profile is a
local diagnostic, not a canonical build artifact.

The first comparison exposed missing IPC serialization consumers: work in the
process-pool transport happens outside the active profiled test context.
`engine/ipc.py` adds conservative dependencies derived from serialization hooks,
their explicit imports and test modules using process execution. These are
source relations, not patch-answer mappings. Dynamic serialization/dispatch
still needs canonical completeness checks.

With this evidence repair and IPC closure, the official sample scorer reports
**250.453 simulated seconds, zero missed patches**. Selector parent CPU was
**1.384249 seconds** locally, child CPU zero for that selection run. The local
sum is about **251.837 seconds**; it is not an official container score or
median. Original baseline: 945.339 simulated seconds. Public sample inspection
informed the diagnostic, so this is not fresh held-out evidence.

The combined map leaves one untrusted lazy-load test and includes 29 observed
fixture-reader records. The complete fixture inventory contains 63 files;
that difference remains explicit. Neither count establishes soundness for all
new changes. Replay-pass omission remains disabled. The remaining path toward
100 seconds is validated input-conditioned exclusions and canonical evidence,
not dropping these safety boundaries.

Local comparison command: use the selector invocation above with
`--index fourthon/rwx_next/reports/combined-local-index.json.gz`.
