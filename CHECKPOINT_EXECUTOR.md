# Architecture decision: restricted query-checkpoint execution

## Strict choice

| Candidate | Decision | Reason |
|---|---|---|
| Larger classifier over current predictors | Reject now | Missing causal inputs and too few independent changes; capacity cannot repair information loss |
| Unrestricted static-name ensemble | Reject | Earlier experiment grew to 380.646 simulated seconds and added analysis CPU |
| Full expensive-test replay | Reject as primary mechanism | TPC-DS verification consumed about 28 CPU seconds for at most 21.454 scheduled seconds |
| Live function replacement in a warm process | Reject | Stale aliases, defaults, caches, descriptors and import-time state are not reliably reconstructed |
| Generic memoization of Python functions | Reject | Mutable arguments, side effects, native state and dynamic dependencies are not sufficiently bounded |
| Restricted baseline query checkpoints | Keep as prototype only | Known inputs and original comparisons can be preserved; measured reuse reduces repeated work, with explicit rejection boundaries |

This is an architecture change for one test family, not another failure classifier. It is not yet a replacement for the whole selector.

## What is implemented

The pinned baseline supplies immutable fixture/table inputs and DuckDB reference DataFrames for the original TPC-DS test: 99 records, 57 with execution enabled. These are baseline artifacts, not answers to mutations. A build-time pass validates each Python result against the original reference and records per-query function-entry dependencies with Python 3.13 monitoring.

For an eligible patch, the new worker loads the baseline checkpoint, reuses queries whose complete observed function footprint does not intersect changed functions, and reruns the affected query computations. Missing footprints cause replay rather than omission. It retains the original expression serialization boundary and DataFrame comparison options. It stops after a faithful failure because the whole numbered test must then be retained.

For replayed queries, it materializes fresh baseline table/schema inputs, preserving aliasing within the used-table subset. Input rows/columns and schema are checked for mutation. Unresolved reconstruction does not authorize pass. Original whole-test runs remain the reference used to evaluate this research adapter.

### Rejection boundaries

- Optimizer/executor body edits only, with preserved signatures, globals, classes, imports and bindings.
- Literal/operator changes and supported Boolean regrouping; new bindings/call structure and dynamic/external-state access are rejected.
- Changes to reused parser, serializer, table representation, reference-computation dependencies and baseline initialization files are rejected.
- Source, fixture/data, capsule, interpreter, package and timezone fingerprints must match.
- Clock/random/user-dependent query inputs are unresolved; comment-only and docstring changes do not silently receive a bytecode-equivalence exemption.
- Unsupported/multiple-file mechanisms remain on the old path. Multiple files are not a blanket rejection if every edit independently satisfies the narrow contract, but mixed fixture/state edits do not.

The dependency footprints are observed baseline evidence, not a proof of complete Python behavior. Fresh table/schema inputs do not prove that every global cache, native or shared-worker state interaction is irrelevant. Eligibility filters and finite comparisons narrow these risks; they do not eliminate them.

## Measurements and failed iterations

| Implementation | Observation |
|---|---|
| Reuse references but reconstruct all tables for every query | Baseline replay about 12.93 CPU seconds; still too much repeated work |
| Materialize only tables used by each query | Baseline replay about 9.7 CPU seconds |
| Add query footprints and failure short-circuit | Unobserved-function change about 0.66 CPU seconds, all 57 results reused; join regression detected at its first failing query in about 0.68 seconds |
| Supported executor-body change | All 57 comparisons passed in about 9.85 CPU seconds, versus about 28 for full original-test verification |

Three independently generated join-rule mutations were checked against original whole-test execution: two passed and one failed, matching the incremental outcomes. They remain within one module/family and are not a comprehensive holdout. The existing public join regression also failed in both paths. Baseline comparisons passed. Twenty targeted unit tests pass.

The compressed baseline checkpoint is approximately 3.83 MB (16.56 MB uncompressed), before adding the repository/source-map files. It is stored in the research bundle, not silently added to the deployed image. Runtime storage/memory and the final repository limit still require validation for the actual export.

## Combined counterfactual selection result

`compose.py` reads upstream selections, applies eligibility and a baseline-measured cost gate, and only proposes removing the TPC-DS whole test after a supported passing result. Failure, missing evidence and exhausted budget keep the test selected. It does not read sample answers.

| Item | Local result |
|---|---:|
| Simulated seconds | 193.138 |
| Missed public patches | 0 |
| Upstream cost-gated verifier CPU | 5.843015 s |
| Checkpoint composition CPU | 10.623307 s |
| Combined measured local total | 209.604322 s |

Only actions actually relevant to the upstream selection are charged here. Baseline capture, validation and cost calibration are build-side work; those costs are excluded consistently with the task's scoring rule. The two runtime CPU measurements are summed from sequential research stages. This is a single macOS experiment, not an official container median. Its upstream uses mixed local dependency maps; the organizer result is unknown.

The standalone checkpoint accepts only three of the inspected public patches. The cheap passing unobserved-function case already excludes TPC-DS in the old selector, so that impressive microbenchmark does not produce additional sample savings. The useful new sample omission comes from the supported executor-body case. This is why microbenchmark speed must not be presented as an end-to-end improvement by itself.

## Reproduce

Python 3.13 plus the pinned research dependencies/source are needed. Use only trusted locally built capsules: the payload is pickle, so an arbitrary downloaded capsule must not be deserialized.

```bash
python research/incremental_executor/build.py --source /path/to/pinned/sqlglot --output /tmp/base.pkl.gz
python research/incremental_executor/build_dependencies.py --source /path/to/pinned/sqlglot --capsule /tmp/base.pkl.gz --output /tmp/query-checkpoints.pkl.gz
python research/incremental_executor/evaluate.py --source /path/to/pinned/sqlglot --capsule /tmp/query-checkpoints.pkl.gz --patches /path/to/data/commits --report /tmp/query-report.json
python research/incremental_executor/compose.py --source /path/to/pinned/sqlglot --capsule /tmp/query-checkpoints.pkl.gz --data /path/to/data --upstream /tmp/upstream-selections.jsonl --output /tmp/combined.jsonl --report /tmp/composition.json
```

## Promotion decision

**Experimental scoring update:** at the user's explicit request, the top-level Dockerfile now runs this path for an evaluation submission. The old runtime is retained in `Dockerfile.reference`. This is not a claim that the earlier promotion gates passed. Local Docker access is denied, so the new image build and container score remain unverified. Canonical Linux/amd64 equivalence, whole-test lifecycle/order/state fidelity, native/global cache boundaries, budget enforcement and broader independent mechanism coverage remain incomplete. The statement explicitly permits baseline dependency maps and runtime tests; it does not explicitly endorse every computed checkpoint/reference cache. Preserve baseline-only derivation and resolve that interpretation before deployment. No organizer message has been sent.

Keep the code and measured evidence. Rule out a universal cache or a claim of immunity. Expand this architecture only where reused state and observation dependencies can be bounded and the measured net benefit is positive. No sub-100 or top-three result is established.
