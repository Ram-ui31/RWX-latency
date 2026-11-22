# RWX Blast Radius

Source-derived test selection and worker scheduling for SQLGlot at the organizer's pinned revision, `eb11aec4be8cb2122afe713a4816662c3f0fb2fa`.

The current candidate compiles argument-field dependencies through inheritance and copied dictionaries, records the validation states that can observe a Boolean requiredness change, and verifies remaining original tests only when their measured CPU cost is promising. Unknown changes retain broader coverage and source-reader evidence.

## Measured results

| Evaluation | Scheduled seconds | Selector CPU seconds | Total seconds | Missed patches |
|---|---:|---:|---:|---:|
| Latest user-reported organizer result, older submitted candidate | 280.548 | 8.990 median | 289.538 median | 0 |
| Recommended default (`9812394`), public, native amd64 | 109.440 | 17.773 median | 127.213 median | 0 |
| Twelve frozen argument checks, guarded candidate (`748e3fd`), native | 63.323 | 7.265 median | 70.588 median | 0 |
| Four composed-schema/import checks, guarded candidate (`748e3fd`), native | 55.651 | 1.586 median | 57.237 median | 0 |

Native figures are medians of three actual offline containers. The sixteen additional cases were frozen before labeling and independently ran or accounted for all 1,620 original tests per case. Ten patches caused failures, comprising 1,274 failing whole-test instances across patches; all were retained. This corpus covers argument metadata, composed schemas and an import failure. It does not establish accuracy on the private distribution.

The import case exposed 162 omitted import-related failures in the older broad map. The corrected model selects every catalog test and disables live pruning for that hazard. Workflow [44959722803](https://github.com/Ram-ui31/RWX-latency/actions/runs/44959722803) validated that correction. The full sixteen-case native recheck in [44963605224](https://github.com/Ram-ui31/RWX-latency/actions/runs/44963605224) retained every failure too. Its cache comparison found no native scheduling saving and extra CPU overhead, so reference memoization is excluded from the default.

Final default-build workflow [44965427261](https://github.com/Ram-ui31/RWX-latency/actions/runs/44965427261) passed on `98123948830907202338bcb4a7e2e99b7d9829e0`. Public median total was 127.213368 seconds, versus 130.516737 with group verification disabled and 131.012795 with the older cost estimate. Timing varies across runners and build calibrations; the final default figure is the submission reference, rather than the lowest historical run.

No new organizer score is available. A private score below 150 seconds and a top-three finish remain unverified.

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

The build downloads only the pinned SQLGlot source and locked public Python packages. It validates committed native baseline observation/dataflow maps, freshly calibrates original-test CPU costs. The original full-map rebuild remains in `Dockerfile.rebuild-maps`. Runtime is offline and needs no API keys. Original test execution is charged as selector CPU. Public answers, generated mutation answers and patch-answer lookup tables are absent from the image.

The Docker build is limited to ten minutes in the native workflow. Runtime checks use two CPUs, 4 GB RAM, a read-only root, a 64 MB temporary filesystem and a non-root user. Three native runs are scored by the official public scorer outside the container; container cgroup CPU includes descendants.

The rejected [native reference memoization experiment](NATIVE_REFERENCE_MEMO.md) is retained in `Dockerfile.native-memo` for reproducibility. It preserves SQLGlot computation and the real process pool, but its native CPU cost exceeded the available scheduling saving. It is absent from the default image.

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
