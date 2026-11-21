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
4. Record which tests consume values, keys, raw required-argument metadata, unknown/custom validation states, missing individual arguments and existing required-argument errors. Record test setup/module consumers separately.
5. At selection time, accept only one existing Boolean-token replacement inside a literal class `arg_types` dictionary. Every other source byte, dictionary key and key order must remain identical. Multiple edits, formatting changes, new keys, arbitrary expressions and unsupported definitions retain upstream evidence.
6. Propagate the changed field through the compiled graph. Retain value/reflection readers, affected validation states, shared test setup consumers, source readers and incomplete baseline observations. Other original tests can be removed from the incoming set.
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
| Twelve frozen additional checks, local integrated calibrated candidate | 246.594 | 59.140 | 3.534 | 62.674 | 0 |

The twelve additional cases were frozen before inspecting outcomes. They span array, JSON, string, temporal, math and core expression modules. Every case was labeled by running all 1,620 original whole tests, independently of the selector. Six cases caused failures, comprising 59 failing whole-test instances across patches. Every one remained selected. This is a 76.0% scheduled-time reduction on this particular argument-metadata corpus.

The complete typed baseline passed 1,620 tests and 25,440 subtests. There are 45 passing repository regression checks. They include reused spawned-worker ownership, inherited requiredness, raw observers, shared setup, source binding, exact edit eligibility, subtest failures and failed fixture cleanup.

Native Linux runs use an actual amd64 image, two CPUs, 4 GB memory, no network, a read-only root, a 64 MB temporary filesystem and the submitted entrypoint. CPU comes from the container cgroup, including descendants. Three runs are measured. The native build completed within the ten-minute build limit.

The measured-CPU policy and the twelve independent native whole-suite labels are being evaluated in the subsequent `acc46ab` workflow. See the workflow artifacts for exact results. The organizer has not evaluated either new commit in this report.

## What can be promised

The supported transformation and its conservative fallback behavior are concrete. Every recorded omission has a dependency explanation or a completed original-test pass. Tests are not discarded because a learned score says they probably pass. A failed action cannot authorize omission of incomplete work.

A universal zero-miss guarantee, immunity to arbitrary hidden tests, a private score below 150 and a top-three finish are not established. Python reflection, custom objects, initialization, resource observations and old coverage limitations require care. A fixed program and baseline traces make narrowly audited semantic reasoning possible; they do not turn empirical validation into a general proof.

## Forecast discipline

The public native median of 125.096 seconds is an actual measurement. It is not a private forecast.

A useful sensitivity calculation starts from the known private scheduled time, 280.548 seconds. If a fraction q of that cost receives the 76.0% reduction measured on the twelve argument checks, and the rest remains unchanged, then a scenario is:

`private total ≈ 280.548 × (1 − 0.760 × q) + 18.5`

Under these assumptions, q must be about 70% to get below 150 seconds. Other settings improvements could reduce that requirement; different private mutations, durations or CPU could increase it. We do not know q. It would be misleading to present this conditional scenario as a calibrated confidence interval or claim that the target has been reached.

The next decisive evidence is the exact candidate's organizer evaluation with scheduled time, CPU and missed-patch counts. A private result cannot be inferred by multiplying a public ratio after the earlier transfer failure.

## Risks and fixes

| Risk | Implemented response | Remaining limitation |
|---|---|---|
| Import reads invalidate nearly everything | Separate initialization from key/value/validation observations; compile derived state | Other initialization transformations remain broad |
| Missing inherited or copied metadata | Validate propagation across all loaded expression subclasses; refuse unresolved graphs | Newly supported source revisions require rebuilding and auditing |
| Required-argument error order changes | Retain tests with existing missing required arguments | Conservatism can keep unaffected tests |
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
* Sample-ratio private forecasts were poorly calibrated. Do not repeat them.

## Research and company approaches considered

* [RWX's task DAG and content-based caching](https://www.rwx.com/blog/mint-launch) suggests representing the dependency that actually changed, instead of rerunning all transitive work. Here the representation is an argument-field dependency graph.
* [Semantics-modifying change reasoning, ISSTA 2023](https://2023.issta.org/details/issta-2023-technical-papers/46/More-Precise-Regression-Test-Selection-via-Reasoning-about-Semantics-Modifying-Change) supports specializing change-impact rules to observable semantic effects. Its published speedups do not predict this competition's score.
* [AccMut: equivalence modulo states](https://arxiv.org/abs/1702.06689) motivates checking whether a mutation actually changes an observed state. This implementation applies a restricted validation-state analogue; it does not implement AccMut.
* [Meta's predictive test selection](https://engineering.fb.com/2018/11/21/developer-tools/predictive-test-selection/) uses historical outcomes and a learned failure model. We lack comparable representative private-distribution history. A learned omission threshold is not justified here, especially with a 300-second missed-patch charge.
* Public entry READMEs emphasize typed data dependencies, differential initialization, isolated tests, budgeted probes and held-out mutation checks. Their self-reported scores are not our measurements. No competitor implementation was copied. See [the repository review](PUBLIC_REPOS_AND_NEXT_STEPS.md).
