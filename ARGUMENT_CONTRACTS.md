# Argument contracts and CPU-aware verification

## Decision

Replace broad import-time invalidation for a precisely supported class of edits with a compiled dependency model of argument validation. Use original-test execution for remaining uncertainty, and price that execution with CPU measurements from the build environment.

This is a substantial change in dependency representation. It does not train on the public answers or predict that an unobserved failure is unlikely. It asks whether this exact source change can alter an observation made by an original test. Unsupported changes retain the upstream selection.

## What the private result actually says

The user supplied these measurements for the previously submitted candidate:

| Run | Scheduled seconds | Selector CPU seconds | Missed patches | Total seconds |
|---|---:|---:|---:|---:|
| 1 | 280.548 | 8.740 | 0 | 289.288 |
| 2 | 280.548 | 8.990 | 0 | 289.538 |
| 3 | 280.548 | 9.100 | 0 | 289.648 |

The median is 289.538 seconds. Scheduling accounts for roughly 97% of the score. Making Python twice as fast would save about 4.5 seconds. To finish below 150 with 18.5 seconds of selector CPU, scheduled work must fall below 131.5 seconds. The required change is in what must run, rather than interpreter speed alone.

The earlier public improvement transferred poorly. Two familiar sample patches accounted for 71.85% of its simulated saving. That evidence could establish those optimizations, but could not establish a comparable improvement on another patch distribution.

## The missed distinction

`arg_types` serves several purposes in the pinned program:

* Iteration, membership and argument-position construction consume dictionary keys and their order.
* Class initialization derives `required_args` from Boolean values.
* Other classes inherit the map or copy it with dictionary unpacking.
* Validation consults required arguments and the arguments present on each expression.
* Tests and reflection can inspect metadata directly.

A change from an optional argument to a required one preserves all key-only behavior. It can change validation only where that argument is missing, or where existing validation errors might be reordered. Treating every importer as a consumer loses this distinction and selects hundreds of unrelated tests.

Ignoring initialization would be incorrect too: changing a base class can affect its descendants and maps copied into other classes. The new compiler represents that propagation explicitly.

## Implemented flow

1. Run the complete pinned baseline with receiver-qualified metadata observations. Both application and original test code are instrumented. Values, descriptors and process serialization remain original.
2. Assign every real pool task its current whole-test owner. A persistent worker must not attribute later tasks to the test that first started it.
3. Compile argument-value origins through inheritance, literal dictionaries, dictionary unpacking and supported constant copies. Validate the computed maps against the actual initialized program. The current source resolves all 1,076 expression classes, with zero unresolved classes.
4. Record which tests consume values, keys, raw required-argument metadata, unknown/custom validation states, missing individual arguments and multiple existing required-argument errors. A single unchanged error has no relative order to change; a changed missing field is retained separately. Record test setup/module consumers separately.
5. At selection time, accept only one existing Boolean-token replacement inside a class `arg_types` dictionary, including validated dictionary unpacking. Every other source byte, dictionary key and key order must remain identical. Multiple edits, formatting changes, new keys, arbitrary expressions and unsupported definitions retain upstream evidence. A shared import-time validation hazard selects every catalog test and disables live pruning for that patch, because imports and global initialization can change outside the compiled argument graph.
6. Propagate the changed field through the compiled graph. Retain value/reflection readers, affected validation states, shared test setup consumers, source/code/resource readers and incomplete baseline observations. Other original tests can be removed from the incoming set. Source/code/resource guards cannot undo a required widening after an import hazard.
7. Apply measured-cost original-test verification to remaining candidates. Preserve failed, skipped, timed-out and unexecuted whole tests. Preserve original class fixtures, subtests and spawned process behavior.
8. Optimize the worker schedule using the official recorded durations and worker charges.

The dependency graph, reader artifact, source index and Python/package/platform environment are bound together by hashes and a versioned manifest. Artifact mismatches fail conservatively. Generated mutation patches and their labels are absent from the image and are never consulted by the selector.

## Evidence obtained so far

These measurements distinguish scheduled time from CPU and distinguish public inputs from independent mechanism checks.

| Evaluation | Earlier scheduled time | New scheduled time | New CPU | New total | Misses |
|---|---:|---:|---:|---:|---:|
| Public, native Linux, CPU-budget predecessor | 113.110 | 113.110 | 22.040 median | 135.150 median | 0 |
| Public, native Linux, compiled contracts (`a4f7ca9`) | 113.110 | 106.577 | 18.519 median | 125.096 median | 0 |
| Six initial argument checks, local compiled model | 147.008 | 15.249 | measured separately | — | 0 |
| Twelve frozen additional checks, local latest guarded/live-import candidate | 246.594 | 60.196 | 6.605 | 66.801 | 0 |

The twelve additional cases were frozen before inspecting outcomes. They span array, JSON, string, temporal, math and core expression modules. Every case was labeled by running all 1,620 original whole tests, independently of the selector. Six cases caused failures, comprising 59 failing whole-test instances across patches. Every one remained selected. The latest guarded candidate gives a 75.6% scheduled-time reduction on this particular argument-metadata corpus. The earlier 59.140-second result preceded the explicit external/resource observation guard and must not be quoted as the latest candidate.

The complete version-nine typed baseline passed 1,620 tests and 25,440 subtests in 97.43 local seconds. A separate check exercised the pinned original validation method across 16,384 four-field state transitions and 16 hash seeds. All 6,912 transitions classified unchanged preserved the exact error list; 8,274 other transitions changed it and remained outside that equivalence claim. This finite check supports the order rule without proving it for arbitrary Python objects. There are 57 passing repository regression checks. They include reused spawned-worker ownership, inherited requiredness, raw observers, shared setup, source binding, exact edit eligibility, subtest failures and failed fixture cleanup.

Native Linux runs use an actual amd64 image, two CPUs, 4 GB memory, no network, a read-only root, a 64 MB temporary filesystem and the submitted entrypoint. CPU comes from the container cgroup, including descendants. Three runs are measured. The native build completed within the ten-minute build limit.

The measured-CPU policy passed native public runs on `acc46ab` with a 120.655-second median, versus 124.002 with group verification disabled and 120.877 with the older cost estimate. The native mutation-labeling harness then failed before labeling: its mounted script incorrectly indexed the parent of a root-level path. That harness path has been fixed. Source/code/resource observers are now explicitly preserved through metadata refinement; the original lazy-import test is eligible for measured-cost live verification, preserving its child interpreter. The later composed/import revision completed all native checks on commit `748e3fd`: public median 125.726840 seconds, twelve-case median 70.587812 seconds and four-case median 57.237053 seconds, with zero missed patches in every run. The organizer has not evaluated this candidate; these are public and independent mechanism measurements.

## Composed schemas and import failures: a second gap found

The compiler already modeled dictionary unpacking, but the initial edit recognizer required `ast.literal_eval` of the complete dictionary. This silently rejected important roots such as Select, Subquery, TryCast and ConcatWs. The recognizer now accepts one direct Boolean field-token replacement and requires the compiler's validated origin edge. Every other source byte remains unchanged; unpack expressions themselves cannot change.

Four additional cases were frozen and labeled independently. The original test suite accounts for every numbered test, including tests whose files fail collection/import. The reference runner continues after collection errors and never treats unexecuted tests as passing. Compact traceback reporting reduces labeling overhead while preserving original test execution.

| Case | Earlier candidates | Corrected candidates | Failing whole tests | Earlier scheduled time | Corrected scheduled time |
|---|---:|---:|---:|---:|---:|
| TryCast required flag | 451 | 31 | 31 | 27.454 | 5.849 |
| Select expressions flag | 1,315 | 16 | 2 | 36.817 | 6.921 |
| Subquery alias flag | 1,315 | 1,620 | 1,172 | 36.817 | 36.817 |
| ConcatWs flatten flag | 191 | 12 | 12 | 25.860 | 6.064 |

The four-case total is 55.651 scheduled seconds plus 1.335259 local CPU seconds, or 56.986259 total, with zero missed patches. Earlier raw selection cost 126.948 scheduled seconds and omitted 162 failing whole tests on the import-breaking Subquery case, which would add a 300-second charge.

Subquery demonstrated why this guard is necessary: DuckDB's generator parses a SQL template while importing. A new required alias breaks that initialization, and 1,020 numbered tests belong to files that cannot import. Another 152 fail during execution. This single case dominates the combined failure-instance count; the total must not be treated as independent samples of arbitrary private changes. Runtime-only consumers are insufficient for this situation. Widening the selection to all catalog tests preserves those failures at the same scheduled cost in this case. Original-test pruning is disabled for recognized import hazards, avoiding both wasted probes and assumptions about partially initialized global state.

The native composed labels contain 1,215 failing whole-test instances, versus 1,217 locally: the original lazy-load test fails locally in the TryCast and ConcatWs cases but passes natively. All twelve earlier argument labels match exactly across environments. Each platform is evaluated against its own independently executed labels.

The twelve earlier cases remain at 60.196 local scheduled seconds with zero misses. The public sample remains at 109.440 scheduled seconds with zero misses. The composed/import revision passed native validation: public median 125.726840 seconds, twelve-case median 70.587812 seconds, four-case median 57.237053 seconds, all with zero misses; the prior `c919952` native build measured a 125.085359 public median and a 70.821082 median on the twelve earlier checks, both with zero misses. That predecessor did not contain the new import guard and is not the recommended final revision.

## What can be promised

The supported transformation and its conservative fallback behavior are concrete. Every recorded omission has a dependency explanation or a completed original-test pass. Tests are not discarded because a learned score says they probably pass. A failed action cannot authorize omission of incomplete work.

A universal zero-miss guarantee, immunity to arbitrary hidden tests, a private score below 150 and a top-three finish are not established. Python reflection, custom objects, initialization, resource observations and old coverage limitations require care. A fixed program and baseline traces make narrowly audited semantic reasoning possible; they do not turn empirical validation into a general proof.

## Forecast discipline

The corrected candidate's public native median of 125.726840 seconds is an actual measurement. It is not a private forecast.

A useful sensitivity calculation starts from the known private scheduled time, 280.548 seconds. If a fraction q of that cost receives the approximately 75.6% reduction measured on the twelve argument checks, and the rest remains unchanged, then a scenario is:

`private total ≈ 280.548 × (1 − 0.756 × q) + CPU`

With 16–20 seconds of CPU, q must be approximately 69–71% to get below 150 seconds under these assumptions. Other settings improvements could reduce that requirement; different private mutations, durations or CPU could increase it. We do not know q. It would be misleading to present this conditional scenario as a calibrated confidence interval or claim that the target has been reached.

The next decisive evidence is the exact candidate's organizer evaluation with scheduled time, CPU and missed-patch counts. A private result cannot be inferred by multiplying a public ratio after the earlier transfer failure. The real Chrome scorer session was checked too: it requires the registered email and a one-time code, so autonomous private evaluation is currently blocked by sign-in. The sign-in page is left ready for the user.

## Additional CPU work examined

Direct original TPC-DS verification cost 28.048 CPU seconds with the host default pool size and 19.556 with two real spawned workers; both lacked the required margin against its scheduling saving. Profiling then located 9.865 CPU seconds in native reference generation. [NATIVE_REFERENCE_MEMO.md](NATIVE_REFERENCE_MEMO.md) documents the narrower memoization experiment, its exact cache checks, preserved original computation and completed native ablation. Native baseline cost was 20.450154 CPU seconds, so no action qualified and the stage only added overhead. It is rejected from the default build.

## Next decision after private feedback

Keep the tested architecture fixed until its organizer breakdown arrives. If scheduled time remains high, first examine unsupported initialization/data families and the remaining scalar-settings test-file heuristic. Version-nine instrumentation now observes original test code, so a future refinement can replace that older file-text approximation with actual receiver-qualified readers, while preserving source/code/resource guards. If CPU dominates, prioritize cheap uncertain obligations and reduce unsuccessful group probes. If any patch is missed, reproduce and repair attribution or an omission contract before optimizing cost again. Do not choose another architecture from the public total alone.

## Risks and fixes

| Risk | Implemented response | Remaining limitation |
|---|---|---|
| Import reads invalidate nearly everything | Separate initialization from key/value/validation observations; compile derived state | Other initialization transformations remain broad |
| Missing inherited or copied metadata | Validate propagation across all loaded expression subclasses; refuse unresolved graphs | Newly supported source revisions require rebuilding and auditing |
| Required-argument error order changes | Retain tests with multiple existing missing required arguments and each changed missing field | Conservatism can keep unaffected tests |
| Custom containers or deceptive runtime types | Record unknown states and retain their tests | Pinned-source reflection coverage is still an engineering assumption |
| Test module/class setup stores derived state | Retain consumers of shared test setup | Shared observations can be broad |
| Reused process workers corrupt attribution | Attach and restore ownership on every real submitted task | Missing worker reports prevent baseline-pass authorization |
| Source/line-table observers see nonsemantic text changes | Require an exact Boolean token replacement; preserve source readers | Other edit families need their own metadata guards |
| Native CPU differs from Mac CPU | Build-local original-test cost calibration; native policy comparison | Costs are estimates, not hard bounds or failure probabilities |
| Verification encounters a failure or broken cleanup | Stop, retain incomplete work; invalidate passes after lifecycle errors | Test-order/global-state effects require continued validation |
| Public tuning overstates generalization | Frozen module-spanning independent full-suite checks | This corpus covers metadata, not the full private distribution |

## Dead ends

* Broad original-pytest verification spent 35.616 CPU seconds to save 0.428 scheduled seconds. Reject it.
* Broad minimal unittest verification was approximately break-even locally and slower natively. Gate actions by measured CPU instead of historical test durations alone.
* A warm-fork experiment increased CPU to 33.160 seconds while saving only 19.254 scheduled seconds. It is not the default.
* Per-patch differential imports established the argument propagation mechanism but added roughly 0.7 local CPU seconds per eligible patch. Compile that dataflow once during the baseline build instead.
* A scalar-settings-only refinement could not handle dictionary values or derived `required_args`. It remains useful for its supported fragment but is insufficient as the base representation.
* Plain AST equality overlooks source bytes and line-table observers. It is insufficient edit eligibility for this refinement.
* Native reference memoization saved about five total seconds locally, but its native baseline cost rose to 20.450154 CPU seconds; the gate declined every action and stage overhead worsened public and held-out totals by about 0.6 seconds. Keep it out of the default image.
* Sample-ratio private forecasts were poorly calibrated. Do not repeat them.

## Competition target

At the browser check on 22 November 2026 (IST), the practice leaders were 114.6, 118.8 and 120.2 seconds. This is a changing public snapshot, not final results. A private result below 150 is an intermediate goal; it does not presently satisfy the original top-three practice objective. Final ranking uses unseen changes.

## Research and company approaches considered

* [RWX's task DAG and content-based caching](https://www.rwx.com/blog/mint-launch) suggests representing the dependency that actually changed, instead of rerunning all transitive work. Here the representation is an argument-field dependency graph.
* [Semantics-modifying change reasoning, ISSTA 2023](https://2023.issta.org/details/issta-2023-technical-papers/46/More-Precise-Regression-Test-Selection-via-Reasoning-about-Semantics-Modifying-Change) supports specializing change-impact rules to observable semantic effects. Its published speedups do not predict this competition's score.
* [AccMut: equivalence modulo states](https://arxiv.org/abs/1702.06689) motivates checking whether a mutation actually changes an observed state. This implementation applies a restricted validation-state analogue; it does not implement AccMut.
* [Meta's predictive test selection](https://engineering.fb.com/2018/11/21/developer-tools/predictive-test-selection/) uses historical outcomes and a learned failure model. We lack comparable representative private-distribution history. A learned omission threshold is not justified here, especially with a 300-second missed-patch charge.
* Public entry READMEs emphasize typed data dependencies, differential initialization, isolated tests, budgeted probes and held-out mutation checks. Their self-reported scores are not our measurements. No competitor implementation was copied. See [the repository review](PUBLIC_REPOS_AND_NEXT_STEPS.md).
