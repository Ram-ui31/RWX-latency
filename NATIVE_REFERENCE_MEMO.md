# Native reference memoization

This revision addresses an observed cost, rather than changing the prediction threshold. On the pinned executor test with two real spawned workers, setup used 0.620 CPU seconds, native reference generation used 9.865 CPU seconds across 57 calls, and the complete test used 18.195 CPU seconds after imports. A separate ordinary pytest calibration used 19.556 CPU seconds. Direct TPC-DS verification therefore exceeded its useful scheduling saving.

The prototype reuses only deterministic native database reference frames. It still runs the original CSV/database setup, SQLGlot parsing and execution, real spawned process pool, argument/result serialization, pandas assertions and class cleanup. No SQLGlot execution results are cached. No patch outcomes are stored.

For each original call to `cached_execute`, it runs the original SQLGlot transpilation under the patch. A reference frame is reusable only when the resulting DuckDB SQL is byte-identical to the SQL that actually produced the stored baseline frame. It also checks fixture hashes, the original test source, Python/package/platform identity, timezone and the artifact digest. Volatile queries and unknown keys are unresolved. The complete original reference-call inventory must be observed before a pass can authorize removing the whole test.

This matters because caching by the input SQL alone would be wrong: a patch can change how SQLGlot transpiles that same SQL, changing the test's native reference. The new key explicitly checks that path live.

Eligibility is restricted to one source-only Boolean argument-field edit in the validated argument graph. Shared import hazards are excluded. Other source edits and data changes keep their existing verification path. A completed original assertion failure, missing reference key, changed native SQL, timeout or failed fixture cleanup cannot authorize omission.

The baseline build measured 8.760 local CPU seconds with memoization, with all 57 reference calls and assertions complete. Three metadata controls matched ordinary original-test results and used 9.284, 9.401 and 9.367 CPU seconds, versus approximately 19.2–19.5 for original pytest. A real serializer regression and an import-breaking regression both remained failing, with zero reference-cache hits. The original real process boundaries were preserved.

In the integrated local twelve-case corpus, scheduled time fell from 60.196 to 45.666 seconds; total cost fell from approximately 66.7 to 61.6 seconds with zero misses. Native Linux rejected that CPU trade. Runtime authorizes an action only if its measured build-local baseline cost plus a 25% margin is below the actual scheduling saving and remaining CPU budget. The completed native ablation compared the enabled and disabled configurations on the same image and inputs, commit `3bf3bbe178a4243ad82b4674ff7b118bdadd3396`, workflow [44963605224](https://github.com/Ram-ui31/RWX-latency/actions/runs/44963605224).

| Native evaluation | Cache stage enabled | Cache stage disabled | Scheduled time, both | Misses |
|---|---:|---:|---:|---:|
| Public, median of three | 126.319098 | 125.687700 | 109.440 | 0 |
| Twelve argument checks, median of three | 71.606717 | 70.950210 | 63.323 | 0 |

The native baseline passed all 57 reference calls but cost **20.450154 CPU seconds**, versus 8.759612 on the Mac. The cost gate rejected every native action because that exceeded both the useful saving and the stage budget. Loading/checking the unused stage still added approximately 0.63–0.66 seconds to the total. The four composed/import cases also retained every native-labeled failure.

**Decision:** reject memoization as a default optimization. `Dockerfile.native-memo` retains the exact experiment; the recommended `Dockerfile` neither builds nor loads the oracle cache. Do not reduce the margin or override calibration just to force its local saving onto native hardware.

The cache is not a general proof for arbitrary Python tests, volatile database workloads or performance-only regressions. It is scoped to this pinned functional integration test and immutable public fixtures. Its use must remain disabled or gated away when its preconditions or measured cost do not hold. It does not establish a private score below 150 seconds.
