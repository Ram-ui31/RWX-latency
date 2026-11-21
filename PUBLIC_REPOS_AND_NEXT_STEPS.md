# Public RWX entries and the next architecture

Reviewed on 21 November 2026. Repository summaries come from public README files fetched directly through GitHub's API. This is a planning review. The competing programs were neither executed nor benchmarked by this review. No competitor source or map was added to our candidate.

## Competitive target

The retrieved official leaderboard snapshot listed Aqua at 126.1 seconds, 67 at 130.3, fortnite pirate token at 134.3, 1212 at 135.3 and VibDiv at 138.2. Rank badges were used because the extracted display order was shuffled. The snapshot had 278 RWX teams. These scores can change.

The user reports 289 seconds for the newer candidate, versus 304 previously. This is a 15-second or 4.93-percent organizer improvement. The local public median improved from 210.415 to 140.429 seconds, a 33.26-percent reduction. That local ratio transferred poorly. The earlier 203-second projection is superseded. A one-third reduction from the current 289 requires about 192.7 seconds. The competitive planning target remains 125–130 organizer seconds, approximately 55–57 percent below 289.

Sources

- https://www.joinbuilders.org/buildathon/leaderboard
- https://www.joinbuilders.org/buildathon/tracks/blast-radius

## Public entry repositories found

These repositories explicitly identify this challenge, the pinned SQLGlot source, or its input/output contract. Public entry status is verifiable from the repository description or README. Acceptance by the scorer and association with the leaders above could not be independently established.

| Repository | Publicly described method | Evidence qualification |
|---|---|---|
| TejayHall/blast-radius | Isolated baseline traces, differential imports, per-key container readers, cost-aware runtime verification and packing | README makes strong soundness claims. This review did not reproduce them |
| Not-Ethan/blast-radius-selector | Receiver-class coverage, bound-name and key dependencies, economical test execution, fixture-case validation and call probes | Reports 109.5 public simulated seconds against a 94.4 oracle, zero misses. CPU excluded from that table. Reports additional generated validation sets |
| JWHaan/shrapnel | Isolated traces, receiver MRO, per-task coverage, primitive comparison operands, economical runtime checking | Algorithm description available. No organizer score verified |
| tfeng12753/shrapnel | Pool-task attribution with serialization, typed setting readers, comparison relations and budgeted probes | Reports public container median 168.0 total. Reports local experimental 113.877 simulated with relations/probes. Different validation levels are stated |
| buidangnguyen05/builders-buildathon-blast-radius | Coverage, fixtures, semantic differences, synthetic mutation generator and separate label/evaluation tooling | Reports practice 206.1 and public 191.257 for older versions. Those are self-published historical measurements |
| viktor-lorentz/blast-radius | Coverage/import maps, semantic classification, narrow constant/settings treatment and small-candidate runtime checks | README summary only. No organizer score verified |
| renxiaocheng/rwx-blast-radius-buildathon | Linux amd64 coverage, spawned-task attribution, fixture readers and scheduling | Baseline coverage design, without an independently verified score |

Repository links

- https://github.com/TejayHall/blast-radius
- https://github.com/Not-Ethan/blast-radius-selector
- https://github.com/JWHaan/shrapnel
- https://github.com/tfeng12753/shrapnel
- https://github.com/buidangnguyen05/builders-buildathon-blast-radius
- https://github.com/viktor-lorentz/blast-radius
- https://github.com/renxiaocheng/rwx-blast-radius-buildathon

Dannyzhang2022/RWX-Blast-Radius-final and darpan-14/RWX also explicitly identify RWX entries through their GitHub descriptions. Their retrieved READMEs largely contain the organizer starter text. The README alone does not establish their current architecture.

- https://github.com/Dannyzhang2022/RWX-Blast-Radius-final
- https://github.com/darpan-14/RWX

## What the review establishes

Basic coverage and worker packing are common approaches. Several entries publicly describe finer evidence about receiver classes, settings, dictionary keys, case-level execution and import-time derived state. Our baseline comparison recorder therefore addresses one part of a larger selection problem.

The most valuable next change is a richer representation of observable state and its consumers. A module import can create thousands of objects while a particular test observes only a small subset. Our fallback currently conflates those relationships.

Public claims about soundness, no-ops and inline process pools require independent testing. Docstring observers, memory behavior, serialization, process initializers and teardown can invalidate convenient simplifications. The official rules require independently authored team code and prohibit prepared patch-answer tables. Our implementation should continue to derive its artifacts from the pinned baseline.

## Interpretation of the 289-second organizer result

The hidden improvement is 15 seconds. The paired public improvement was about 70 seconds. We therefore have direct evidence that the public sample overstates the reach or benefit of the latest optimizations on the practice batch.

Possible causes include a different frequency of supported edits, more initialization changes, more conservative fallbacks and different live-verification costs. Without the supplied per-run cost breakdown, their relative contributions remain unknown.

A scored total below the 300-second penalty implies that the run corresponding to that total incurred no missed-patch penalty under the documented formula. The median score alone does not establish all three individual runs' miss counts.

Do not lower selection thresholds to chase 130. First improve dependency precision and use a wider independent validation distribution. Benchmark every next design against the exact 289-second candidate and its native artifacts.

## Our measured remaining opportunity

The current public candidate schedules 136.028 simulated seconds. The exact public failure-only scheduling oracle from our existing audit is approximately 94.351 seconds. Thus about 41.677 simulated seconds remain recoverable on this already-inspected public sample. Runtime CPU is about 4.4 seconds.

Three import-time edits currently cost 9.499, 7.890 and 9.233 seconds, respectively. Together they account for 26.622 seconds. Their baseline public oracle gap is large, but these particular patches are already inspected and cannot serve as fresh validation.

Two patches genuinely fail TPC-DS. Selecting that whole test accounts for an unavoidable 42.908 seconds of recorded test time across those two patches, before worker costs. Removing a test that actually fails cannot reduce the valid oracle. Further efforts must focus on unnecessary selections and selector CPU.

This cost accounting rules out another generic full-suite replay layer as the principal next step.

## Proposed architecture

Use demand-driven validation of observable state, supported by fresh baseline dependencies.

### 1. Native isolated baseline evidence

Run baseline tests with isolation sufficient to attribute lazy imports and warmed caches. Record whole-test setup, call and teardown, child work, source readers and uncertainty. Collect receiver class/MRO, executed attribute-read locations and dictionary-key consumers.

Build the map in native Linux amd64 using the exact lock. Map generation can run in a separate reproducible development workflow if it exceeds the ten-minute submission build limit. Committed baseline maps need builder, source, environment and payload fingerprints and must fit the repository size limit.

Promotion gate

- All numbered tests have explicit complete or incomplete status.
- Spawned execution is attributed to the submitting whole test.
- Actual original process behavior remains the reference for validation.
- Baseline/import errors have conservative propagation.
- Fresh independent tests expose cache warmup and aliasing defects.

### 2. Import-time state differences and provenance

For supported constant, class-setting and dictionary-entry edits, compare baseline and patched initialized state in fresh isolated processes. Capture receiver-qualified attributes, callable identities and normalized values. Follow reverse import dependencies so derived values are compared too.

Examples include expression argument definitions producing required-argument sets, and dialect settings being copied into parser/tokenizer tables. A changed source dictionary entry can affect several derived objects. A test is irrelevant only when its observable state dependencies are unchanged.

Read provenance must handle inherited attributes, aliases, dictionary copies, iteration and computed access. An iterator reads the relevant container broadly. Dynamic or unresolved propagation retains the existing broader candidate set.

Initially support literal data edits with stable initialization only. Unknown imports, nondeterminism, metaclass behavior or an import timeout retain importers. Never assume that a matching digest alone captures every externally observable effect.

Expected value

This attacks the 26.622-second public import-time cluster directly and should generalize to unseen settings edits. That figure is an opportunity bound, not promised savings. Measure changed-state import CPU before deciding whether runtime comparison pays.

### 3. Case-level obligations for slow tests

Represent a whole test as lifecycle obligations plus its fixture cases. Each case gets its baseline inputs, read dependencies, executed regions and original assertions.

For a patch, unchanged supported obligations may be reused. Execute every affected obligation. Preserve every setup, teardown, shared-state and post-loop check. A whole test can be omitted only when every obligation is discharged. One failure or unresolved obligation retains the entire test.

Start with optimizer fixture tests that have independent cases and straightforward assertions. Extend expensive executor cases only after original-process equivalence checks. Memory and process-behavior tests require their original execution.

This extends our earlier query-checkpoint direction to a principled whole-test obligation model. It must cover both original parsing/reference behavior and the changed execution path.

### 4. Expand expression observations by a restricted interpreter

Extend the existing operand recorder to literal-bound scalar expressions, exact built-in arithmetic and tuple/index boundaries where evaluation has no custom dispatch or side effects.

Keep unknown flags, overflow/exception behavior, repeated invocations and evaluation order. Boolean short-circuit substitutions need special care because the new program may evaluate an operand that the baseline never evaluated. An unseen operand cannot receive a fabricated value. Keep those cases selected unless a supported independent check resolves them.

Arbitrary function-call snapshots and arbitrary AST evaluation are deferred because mutable aliases, globals, descriptors and effects make equivalence difficult to establish.

### 5. Joint validation budget

Choose actions by marginal schedule saving, including startup, source overlay, imports, executed tests and rescheduling costs.

For an action with pass probability p, schedule saving delta, and complete CPU cost e, its optimistic expected benefit is p times delta minus e. Budgeting may use estimates. Omission still requires evidence from the chosen validation mechanism.

For heuristic omission without verification, expected miss penalty is 300 times the probability of missing any failing test on that patch. A 2-second saving would require miss risk below about 0.67 percent even before uncertainty costs. Correlated test failures make independent per-test risk estimates unreliable.

Keep policy decisions at patch level. Never infer that finding one failure identifies every failing test.

## Execution order and acceptance

| Order | Work | Measure before expanding |
|---|---|---|
| 0 | Preserve the 289-second submission and capture per-run simulated/CPU/miss totals | Distinguish excess selected work from live-verification CPU. The local ratio already failed to transfer |
| 1 | Build native receiver/attribute/key and lifecycle evidence | Baseline completeness, build cost, artifact size |
| 2 | Implement restricted initialization-state/provenance analysis | Score reduction per CPU second, independent mutation recall |
| 3 | Add optimizer case obligations | Whole-test equivalence including lifecycle and failing subtests |
| 4 | Extend safe expression observations | Unseen operator/constant families and boundary cases |
| 5 | Optimize joint validation and scheduling slack | Median total cost across repeated native runs |

The new classifier or planner must produce inspectable evidence for every omission. Unknown dependencies, new structures, signatures and unsupported state changes retain the conservative path.

## Validation design

Create a new mutation corpus independently of competitor artifacts. Divide by source module and edit mechanism before inspecting outcomes. Include import failures, class-setting values, dictionary keys, inherited aliases, multi-file interactions, exception paths, source metadata, fixtures, serialization and process behavior.

Label with the original pinned tests in the target environment. Keep all mutation labels outside shipped maps and runtime inputs. Use separate development and untouched validation groups. Repeatedly tuning on a group makes it development data.

Report whole missed patches, total score, CPU, unresolved fraction, false selections, per-family failures and artifact provenance. Zero misses across N independent representative patches gives an approximate 95-percent upper miss-probability bound of 3/N. Thirty public patches or four controls provide weak generalization evidence. Related mutants do not supply the independence assumed by that approximation.

Promote after zero observed held-out misses, an improvement in native total score and no unexplained regression in any tested mechanism. A finite corpus supports empirical confidence, not universal immunity.

## Choices ruled out

- A larger classifier over file names and edit counts lacks the missing observable-state evidence.
- A blanket comment/docstring exemption loses source and metadata observers.
- Restricting dictionaries by keyword text alone misses computed keys, aliases and derived state.
- Replacing process pools inline as the sole correctness reference loses process-specific behavior.
- Running every candidate test live can cost more CPU than the schedule it removes.
- Further packing work has limited value before resolving broad import-time selections.
- Copying competing implementations or mutation-answer maps does not establish an independent valid entry.

## Completion criteria

The immediate next architectural experiment is receiver- and key-sensitive initialization-state analysis, followed by optimizer case obligations. The 289-second organizer result increases the priority of broad unseen initialization and dependency cases. It does not identify the private failing cases or establish which cost component dominates. The working competitive goal is 125–130 seconds on the organizer batch. Local evidence should move toward the public oracle while retaining independent mutation recall. Neither an organizer result nor a top-three position is promised by this plan.
