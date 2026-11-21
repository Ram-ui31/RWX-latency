# RWX Blast Radius

Source-derived test selection and worker scheduling for SQLGlot at the organizer's pinned revision, `eb11aec4be8cb2122afe713a4816662c3f0fb2fa`.

The current candidate compiles argument-field dependencies through inheritance and copied dictionaries, records the validation states that can observe a Boolean requiredness change, and verifies remaining original tests only when their measured CPU cost is promising. Unknown changes retain broader coverage and source-reader evidence.

## Measured results

| Evaluation | Scheduled seconds | Selector CPU seconds | Total seconds | Missed patches |
|---|---:|---:|---:|---:|
| Latest user-reported organizer result, older submitted candidate | 280.548 | 8.990 median | 289.538 median | 0 |
| Public, native amd64, preceding contracts (`c919952`) | 109.440 | 15.645 median | 125.085 median | 0 |
| Twelve additional argument checks, local integrated calibrated candidate | 60.196 | 6.605 | 66.801 | 0 |

Public native figures are medians of three actual offline containers. The twelve additional cases were frozen before labeling and independently ran all 1,620 original tests per case. Six patches caused 59 failing whole-test instances; all were retained. They cover one change family and do not establish hidden-distribution accuracy.

The current revision additionally handles composed argument dictionaries and protects import-time validation. Four new cases measured 55.651 scheduled seconds plus 1.335 local CPU seconds, with zero misses. One case exposed 162 omitted import-related failures in the older broad map; the corrected model widens safely. The updated revision is being validated on branch `rwx-native-evaluation-20261121`. The preceding `c919952` native figures above are historical, not validation of that final correction. Its workflow artifacts are authoritative for those measurements. No new organizer score is available. A private score below 150 seconds and a top-three finish remain unverified.

See [the current proposal and risk analysis](ARGUMENT_CONTRACTS.md) for the architecture, evidence, dead ends, research sources and conditional private-score calculation. Earlier development records are retained in [DISTRIBUTION_AUDIT.md](DISTRIBUTION_AUDIT.md), [CPU_TRADEOFF.md](CPU_TRADEOFF.md), [OBSERVATIONS.md](OBSERVATIONS.md) and [the public repository review](PUBLIC_REPOS_AND_NEXT_STEPS.md). Their earlier measurements are historical.

## Build and run

Use native Linux amd64 for performance measurements. Docker emulation on an Apple Silicon Mac can be substantially slower and is not an equivalent timing environment.

```bash
docker build --platform linux/amd64 -t rwx-latency .
docker run --rm --network none --cpus 2 --memory 4g \
  --pids-limit 256 --read-only --tmpfs /tmp:rw,size=64m \
  -v "$PWD/input:/data:ro" rwx-latency > predictions.jsonl
```

The mounted input contains `tests.json` and `commits/*.patch`. Output is one JSON line per patch, with `commit` and `workers` fields and at most eight workers. Diagnostics go to stderr. The schedule uses the supplied recorded test durations and a two-second charge per active worker.

The build downloads only the pinned SQLGlot source and locked public Python packages, runs baseline tests and creates baseline-only observation/dataflow/cost artifacts. Runtime is offline and needs no API keys. Original test execution is charged as selector CPU. Public answers, generated mutation answers and patch-answer lookup tables are absent from the image.

The Docker build is limited to ten minutes in the native workflow. Runtime checks use two CPUs, 4 GB RAM, a read-only root, a 64 MB temporary filesystem and a non-root user. Three native runs are scored by the official public scorer outside the container; container cgroup CPU includes descendants.

## Validation

```bash
python -m pytest -q tests
python3 tools/native_benchmark.py --image rwx-latency
python3 tools/argument_holdout.py --native --image rwx-latency
python3 tools/native_benchmark.py --image rwx-latency \
  --data argument-holdout --output native-argument-results.json
```

The latter commands require Docker on native Linux. Validation patches and independent labels are generated after building and remain outside the image. The labeling harness runs every original whole test, preserving pytest subtests and real process pools.

## Layout

* `run_candidate.py`: protocol entrypoint, conservative stage fallback and orchestration.
* `blast/`: patch parsing, baseline dependency retrieval and worker scheduling.
* `engine/`: checked patched trees, source identity, IPC and original-test execution.
* `research/observations/`: baseline comparison operands and metadata/source observers.
* `research/typed_settings/`: receiver-qualified configuration and validation observations.
* `research/state_diff/`: compiled argument propagation; earlier differential-import prototype retained for research.
* `research/tail_verifier/` and `research/group_verifier/`: measured-cost original-test verification.
* `tools/`: pinned source download and independent native evaluation harnesses.

The older checkpoint design is retained in `Dockerfile.checkpoint`; the static reference is in `Dockerfile.reference`. They are not the default candidate. Embedded source retains SQLGlot's license in `THIRD_PARTY_SQLGLOT_LICENSE`.
