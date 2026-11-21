# Why public improvements transferred poorly

## What is established

The organizer score improved from 304 to 289 seconds, a 4.93 percent reduction. Our earlier paired public measurement improved from 210.415 to 140.429 seconds, a 33.26 percent reduction. The local improvement was a poor predictor.

Two patches supplied 41.035 of the 57.110 simulated seconds saved on the public sample, or 71.85 percent. Repeatedly choosing improvements against those 30 already-inspected patches gave those specific mechanisms disproportionate influence.

The optimized fragment was narrow. It supported a few single-operator substitutions, plain comments and live verification calibrated for the generator memory test. Most other changes retained older broad selections. Unknown private patch composition, private batch size and selector CPU prevent an exact attribution of the remaining organizer cost.

The fixed SQLGlot revision and test catalog are required by the problem. The baseline being changed here is the dependency measurement and evaluation process. The patch distribution is unknown, while the program under test is pinned. This favors program-derived dependencies, complete task attribution and conservative handling of unsupported edits.

## A reproducible profiling error

The new receiver-settings profiler initially selected too few tests and missed the public TSQL WEEK_OFFSET failure.

SQLGlot's optimizer class keeps a spawned ProcessPoolExecutor across tests. A worker inherits environment variables when it starts. Reading the test name from that inherited environment associates later tasks with the worker's first owner.

The initial map associated the TSQL setting read with test_canonicalize. The corrected map associates it with test_simplify, the whole test that actually fails after this mutation.

The correction attaches the whole-test owner to every submitted task. Original spawned workers, original function arguments, argument serialization and result serialization are preserved. A task restores its previous owner on completion. The same ownership correction now applies to our earlier comparison/source-metadata observation build.

This establishes an error in our measurement implementation. It does not reveal the organizer's hidden patches or prove how much of the 289-second score it explains. The older source-index map still has its documented mixed-environment and profiling limitations.

## The implemented next candidate

The build now records reads of uppercase class settings against the actual defining class in the receiver's MRO. An inherited setting is attributed to its defining owner. Computed getattr reads, explicit class dictionaries and vars reads with an argument are observed.

Only a single existing scalar class setting with an otherwise identical AST is eligible. The value's primitive type must be preserved. Shared setup/import reads veto narrowing because initialization may produce derived state. Source readers, direct/reflection readers in tests, memory tests, uncertain tests and unsupported changes keep their existing candidate evidence.

The refinement only removes tests from the incoming candidate set. It preserves upstream evidence that a test has already passed live verification.

This is a restricted runtime dependency map. It uses no patch identifiers, prepared mutation outcomes or private-set guesses. It currently leaves dictionary-entry changes, derived initialization state, new bindings and more complex edits on the broader path.

## Validation

| Evaluation | Previous candidate | Corrected candidate | Missed patches |
|---|---:|---:|---|
| Public sample, simulated | 136.028 s | 125.574 s | 0 for both |
| Public sample, median total across three local runs | 140.429 s | 130.591 s | 0 for both |
| Three fresh settings mutations, simulated | 27.909 s | 11.548 s | 0 for both |
| Fresh settings mutations, median total across three paired local runs | 30.959244 s | 15.663178 s | 0 for both |

The fresh-control median reduction is approximately 49.4 percent. These controls were selected outside the previously optimized public patches, and their original whole-suite failures were obtained before comparing the refinement.

The PostgreSQL, TSQL and Spark mutations were each labeled by running all 1,620 original tests. They broke seven, one and one whole tests respectively. Every failing test remained selected. The raw static candidates reduced from 282 to 19, 166 to 8 and 261 to 5 when compared through the integrated corrected selector. Expensive retained tests were then handled by the existing cost-gated original-test verifier.

The task-aware settings baseline passed 1,620 tests and 25,440 subtests. The corrected comparison baseline also passed those tests. There are 37 passing repository regression checks, including a real reused spawned worker receiving different owners on consecutive tasks and restoring its prior owner afterward.

All measurements here are local ARM macOS measurements. Native Linux amd64 validation is pending. Three settings controls support that mechanism only. They do not estimate the miss rate across the full hidden patch distribution.

## Rejected experiment

A broader original-pytest group verifier saved only 0.428 simulated seconds while consuming 35.615562 CPU seconds. Failure formatting and imports were expensive, and a wall limit did not bound total multi-process CPU tightly enough. The experimental implementation is preserved under research/group_verifier for audit. It is excluded from the default Docker image and selection path.

## Ideas retained from public entry descriptions

Public READMEs from TejayHall, Not-Ethan, JWHaan and tfeng12753 describe receiver-qualified settings, isolation, per-task attribution or state dependencies. Those ideas address an observable weakness in our code. Our implementation was written independently and tested against original SQLGlot execution.

Strong soundness claims, blanket metadata exemptions, keyword-only dictionary narrowing and inline pool substitution were not adopted as guarantees. The repository review and URLs are recorded in PUBLIC_REPOS_AND_NEXT_STEPS.md.

## Remaining work with the highest expected value

1. Obtain native and organizer per-run simulated, CPU and miss totals for this exact candidate. The 289-second result remains the latest organizer measurement.
2. Rebuild the older coverage/source index with isolated lifecycle and task ownership, then compare its dependency sets with the current map.
3. Extend initialization analysis to dictionary entries and derived values, including copies, inheritance, iteration and failed imports.
4. Add fixture-case obligations only after preserving complete whole-test lifecycle and original process semantics.
5. Validate against a larger corpus split by module and mutation mechanism, with untouched holdout groups.

The next selection model should explain omissions through observed dependencies. The local/public ratio will no longer be extrapolated into an organizer score. A competitive organizer result and a top-three finish remain unverified.
