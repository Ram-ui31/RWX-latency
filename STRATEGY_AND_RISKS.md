# RWX: strategy, potential losses and decision gates

21 November 2026. This is a plan, not a claim that the proposed replay engine is implemented or safe for unseen changes.

## Starting point

The current candidate reproduces 234.350 simulated seconds with zero misses on the already inspected public sample, plus approximately 1.88 seconds of local selector CPU. The earlier organizer result reported by the user is 324 seconds on a different set. Its component breakdown is unknown. We cannot infer a missed patch or compare these totals as if they were the same workload. Canonical Docker validation remains outstanding.

The scored runtime currently uses dependency analysis and scheduling. Input-conditioned differential validation exists only as partial research primitives. It has not produced the reported runtime improvement.

## Decision

Keep the current candidate as a recoverable reference. Build one narrow, evidence-driven validation layer alongside it. Expand only after proving both faithful outcomes and positive end-to-end economics. A broad rewrite, a larger network and an ensemble union are not the default next actions.

Priority: framing, then architecture, with robustness built into both; combine methods by responsibility; optimize once the mechanism is validated.

## Five directions: benefits, risks, losses and responses

| Direction | Potential benefit | Risk and loss we could suffer | Strategy and stop condition |
|---|---|---|---|
| Different framing | Resolve whether an affected contract actually fails, rather than retaining every reachable test | A passing probe is mistaken for a whole-test pass. One omitted failing test incurs a 300-second patch penalty. Multiple failing subtests can be collapsed incorrectly | Maintain whole-test ownership and an obligation ledger. A single faithful failure retains the whole test. Pass requires all relevant observations and lifecycle accounted for. Unknown stays selected |
| Different architecture | Incremental execution can reuse unchanged work and isolate small affected computations | Capturing/rebuilding state can cost more CPU than the selection saves. Stale caches or aliasing can make replay diverge. Engineering scope can consume time without a usable result | Implement one optimizer adapter with original assertions and explicit eligibility checks. Keep the old path usable. Reject the adapter if faithful reconstruction is expensive or its boundary cannot be validated |
| More robustness | Better recall on new mechanisms, environments and process boundaries | Blanket widening returns us to hundreds of seconds; confidence-based pruning creates silent omissions. Instrumentation may perturb memory/timing tests | Record completeness by mechanism and test. Localize unknowns only where dependency isolation supports it. Keep native/resource-sensitive tests on original execution/fallback paths. Validate the exact deployment environment |
| Existing methods alongside ours | Dynamic traces, static relationships and original tests cover different gaps | Unioning all outputs causes dependency cascades; intersecting outputs can drop genuine failures. Shared assumptions create correlated blind spots. Extra maps consume build/runtime resources | Assign distinct roles: traces retrieve, static guards add missing dependencies, differential evidence resolves supported observations, whole tests handle unresolved cases. No majority vote establishes safety |
| Optimization | Lower startup, serialization, analysis and repeated work | Faster execution can change import order, process state or timeout behavior. More workers reduce wall time while total CPU rises. Fine tuning can overfit the public sample | Optimize measured hotspots after equivalence. Cache immutable baseline parsing; reset patch-local state. Charge all child CPU, copying and serialization. Retain an optimization only if its measured total improves |

## The architecture and its contract

1. **Retrieve:** use the current dynamic dependency map, initialization handling and additive serialization guards. Record the assumptions of retrieval; a missed candidate cannot be repaired by a later verifier.
2. **Bind:** identify the exact contract inputs, expected values/exceptions, SQL dialect, schema, optimizer rule order, fixture metadata and state dependencies.
3. **Evaluate:** apply an exact local differential check or a validated replay adapter. A scalar expression result covers that expression and binding only.
4. **Resolve:** classify evidence as confirmed failure, supported non-impact, validated pass or unresolved. Changes to control flow, imports, fixtures and expectations invalidate the relevant reused evidence.
5. **Decide:** include every confirmed failure and unresolved whole test, then use the existing scheduler. Stop validating when the remaining actions do not justify their cost or the batch budget is low.

A runtime-confirmed failure must reflect faithful assertion/error semantics. A verifier timeout means unresolved, unless it is an actual timeout of the canonical original test. A harmless-change decision requires complete supported evidence across the candidate/observation scope; it is not a low neural probability.

## Economic model: measure the losses we can actually incur

For selection S, define C(S) as its best available scheduled cost including occupied-worker overhead. Evaluate a validation action using:

    net benefit = C(S before) - C(S after) - all additional runtime CPU

Include action selection, input/state capture, temporary-source preparation, imports, reference execution, serialization and every child process. Report batch wall time and peak temporary storage separately. A faster wall time is not automatically a lower score.

A test's recorded duration is not its marginal saving: removing a short test may leave the busiest worker and worker count unchanged. Conversely, eliminating an expensive critical-path false positive can save substantially more. Prioritize measured marginal cost, not test count.

The missed-patch penalty is discontinuous. An illustrative 30-second saving is canceled by a 0.10 increase in expected missed patches, because 300 * 0.10 = 30. This is sensitivity analysis, not a reliably estimated risk threshold or permission to accept misses. Thirty public changes cannot establish tiny failure probabilities.

Concrete failure costs:

- **Recall loss:** 300 seconds per patch that omits any failing test; not 300 per individual omitted test.
- **CPU loss:** charged even when validation discovers the test passes. Our whole optimizer-test probe used about 10 child CPU seconds; it is not an economical generic default.
- **Fallback loss:** retaining expensive tests repeatedly recreates a structural floor. Removing a guard without evidence is not a fix.
- **Operational loss:** build rejection, malformed output, crash or resource timeout can invalidate the run. Keep output writing independent from optional analysis failure where feasible.
- **Development loss:** a complex adapter can consume the remaining development window. Use a narrow scope and a reproducible reference so unsuccessful work is reversible.

## Staged implementation plan

### Stage 0: freeze and diagnose

Record the exact candidate revision, map hash, dependency provenance and public scorer output. Preserve the current working changes before starting another implementation branch; do not overwrite the current candidate. Capture the organizer receipt's simulated cost, CPU and miss count if available, without waiting for it to begin independent work.

Produce a cost ledger: largest marginal savings opportunities, which tests remain unresolved, why they are included, and analysis CPU per mechanism. Use public labels only in offline diagnostics. The final input distribution remains unknown.

**Gate:** the reference output is reproducible, and the proposed pilot addresses a material cost or correctness gap. A large number of easy tests is not a sufficient reason to choose it.

### Stage 1: optimizer-fixture adapter in shadow mode

Start with one original optimizer-fixture helper. Bind its real input query, expected output, schema, dialect, options, rule order and helper/loader fingerprints. Reuse the original assertion semantics. Handle loader metadata and record ordering explicitly.

Initially support only independently replayable cases. Reject native engine comparison, shared connections, persistent mutation, unresolved process state and cross-record dependencies. Fixture changes use the new loader output and new expected values. Helper/loader changes invalidate the adapter.

Run the adapter beside the original test. Its proposed omissions do not affect the emitted competition selection during this stage.

**Gate:** every discrepancy between proposed evidence and original-test outcome is explained and fixed. No unknown case is labeled pass. This gate validates a supported adapter scope, not arbitrary Python.

### Stage 2: independent challenge set and economics

Prepare mechanism-based challenges before reading their outcomes: source-body changes, new branches, exception paths, schema/dialect changes, fixture metadata/order, altered expectations, coupled multi-file changes, initialization, serialization and state reuse. Separate generator families and source regions. Include harmless variants and multiple failing whole tests.

Use the original relevant tests as an oracle and periodically run the full suite to check candidate retrieval. A shortlist-only oracle cannot reveal failures outside the shortlist. Synthetic validation does not establish final-set recall.

For every action compare baseline selection cost, proposed selection cost and all added CPU. Identify how many real critical-path decisions the supported adapter can resolve. Fixture cases with tiny marginal savings may be useful correctness controls but cannot justify the performance architecture alone.

**Gate:** zero observed false-safe decisions in the frozen challenge suite, positive total net benefit and adequate canonical batch/resource headroom. Report sample size and covered mechanisms. Do not convert zero observed failures into a universal guarantee.

### Stage 3: selective activation

Activate omissions only for contracts satisfying the validated adapter's explicit eligibility conditions. Retain original dependency selection for everything else. If source/helper/environment fingerprints differ, disable that evidence path.

The controller chooses actions from measured costs and conservative cost bounds, with recovery time reserved for writing every required output line. On timeout, bad serialization, incomplete coverage or exhausted budget, retain unresolved tests. Actual CPU/resource enforcement must account for process trees; a parent-process stopwatch is insufficient.

**Gate:** combined simulation plus container CPU improves in repeated canonical runs, without new observed misses or runtime rejection. Compare three-run medians where matching the official harness. Do not enable a whole-source feature based solely on a good public score.

### Stage 4: expand and optimize

Expand next to the adjacent contract family that offers the highest measured net benefit. Executor/table/native-state replay comes later because its state and reference-result semantics are harder. A resource-sensitive test needs a faithful resource contract; a smaller SQL example cannot stand in for its stress behavior.

Optimize immutable baseline indexing and shared setup first. Consider clean-process startup amortization only after validating import/initialization equivalence. Do not use live function hot-swapping or mutable cross-patch caches as shortcuts.

**Stop/rollback:** any false-safe result blocks the affected adapter; unexplained canonical divergence blocks promotion; persistent negative net benefit rejects the adapter's performance hypothesis. Preserve useful context capture and diagnostics even if replay is rejected.

## Role of learning

The first adapter needs no neural model. A later learned component may estimate verification cost, rank unresolved contracts, summarize input/state distributions and expose out-of-support cases. It does not establish pass/non-impact from confidence alone.

Baseline traces cannot reveal every counterfactual outcome. More synthetic labels cannot automatically supply the private change distribution. Outcome-trained weights would need separate eligibility and provenance review before deployment; no such weights are part of this plan.

## Promotion checklist and promises

A candidate needs an exact source/environment identity, accounted whole tests/subtests/lifecycle, validated supported adapters, retrieval audits, full CPU/resource measurements, a frozen evaluation record and a clean export without answer-derived artifacts. Keep unsupported mechanisms visible.

We can promise transparent evidence, measured economics and reversible promotion. We cannot promise test-set immunity, top three or sub-100 before evaluation. The goal is a reusable incremental validator whose fast path is justified by behavior, rather than a progressively less cautious selector.
