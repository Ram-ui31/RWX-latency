# Baseline observations for the next RWX run

The next candidate targets approximately 203 seconds on the batch where the prior entry scored 304 seconds. The measured local public improvement is 33.26 percent. The hidden batch has yet to be measured.

## Why the prior approach plateaued

Statement coverage identifies execution of a changed location. A changed operator can return exactly the same value for every operand encountered by a particular test. Coverage retains that test anyway. The query checkpoint stage can resolve some of these cases, but pays for imports, data copying and query execution during selection.

Patch composition adds excess work. A comment in one module caused the old selector to broaden selection for another executable edit. Source and code metadata readers matter, so an unconditional comment exemption would lose observable dependencies.

## Theory and implementation

For deterministic execution, consider the first operation where the modified program could differ from the baseline. If the operands, result and observable effects agree, execution continues identically until another possible divergence. This motivates recording operand relations at precisely matched edit sites.

The implementation supports a narrow fragment.

- For a single identity-to-equality substitution, every recorded invocation must have identical comparison results and use a supported side-effect-free equality implementation. Distinct equal strings invalidate omission. Arbitrary equality implementations remain unknown.
- For strict-to-inclusive ordering substitutions and the reverse, exact integer, string or integer-tuple operands must never hit equality. Boundary observations retain the test.
- The entire module AST must differ at exactly one supported operator. Additional changes reject this inference. Operand inference is disabled for multi-file patches.
- Plain standalone comments must preserve the AST, including type comments and docstrings. Source readers and readers of changed code metadata stay selected.
- Each file is analyzed independently and its retained tests are unioned.

The argument depends on complete observations, repeatable inputs and captured observables. This Python implementation is an empirical restricted approximation. Arbitrary reflection, concurrency, native extensions, timing sensitivity and future input distributions remain limitations.

## Baseline collection

The build runs the baseline suite with integration tests enabled. The loader instruments identity comparisons and selected literal-bound comparisons. Each whole test receives the union of all observed operand relation flags.

Audit events record which application source files and code objects a test observes. Full source reads guard the file. Code-object observations guard the corresponding qualified function when its compiled representation changes, including source locations.

Shared setup and collection observations veto relevant omissions. Child processes receive the recorder through sitecustomize. Missing process output removes its owner from usable evidence. External-process and memory-observing tests are excluded from usable pass evidence. Source hashes, interpreter/package fingerprints and the source-index digest bind observations to the build. IPC closure is computed during the build.

The map contains generic baseline execution facts without patch identifiers or prepared mutation outcomes.

## Runtime

1. Verify the observation fingerprint and source-index digest.
2. Apply existing coverage, fixture and IPC evidence per changed file.
3. Apply supported operand and comment observations, preserving metadata readers.
4. Union retained tests and optimize worker assignments.
5. Consider only original tests with passing baseline cost measurements for live verification. The current calibration covers the generator memory test.
6. Retain a test after a timeout, failure or unresolved result. Remove it after its original whole-test validation passes.
7. Emit protocol output through the existing entrypoint.

The default candidate ends after this stage. Dockerfile.checkpoint preserves the earlier query-checkpoint candidate.

## Measured comparison

Both entrypoints used the same public 30-patch sample, interpreter, machine, catalog, original-test runner and freshly rebuilt compatible assets. Every measured run had zero missed patches. CPU includes child processes.

| Candidate | Simulated seconds | Three CPU measurements | Median total seconds |
|---|---:|---|---:|
| Earlier checkpoint entrypoint | 193.138 | 17.276888, 17.531569, 17.130825 | 210.414888 |
| Baseline observations | 136.028 | 4.413475, 4.401134, 4.358928 | 140.429386 |

The reduction is 69.985754 seconds, or 33.26 percent. Applying that ratio to 304 gives approximately 202.89 seconds. This is a scenario estimate. Hidden-patch composition and Linux timings can change the reduction.

An ablation using simulated time alone measured 234.350 seconds with per-file composition, 205.003 seconds after adding guarded comments, and 157.930 seconds after adding operand observations. All three had zero public misses. Economical original-test verification reduced the final simulated time to 136.028 seconds.

The repository regression suite passed 34 checks, including custom equality, distinct equal strings, ordering boundaries, metadata attribution and entrypoint routing.

The observation build passed 1,620 original tests and 25,440 subtests locally. It produced 800 comparison sites and usable evidence for 1,618 tests. Excluded tests observe external processes or memory.

Fresh independent controls ran the complete original catalog. A plain-comment patch passed all tests. A mixed comment plus CTE-boundary mutation failed whole tests 1324 and 1336. Both remained selected. A separate numeric-boundary mutation passed the suite. A new select-count boundary mutation failed five whole tests. All five remained selected among 20 selections.

Local measurements used ARM macOS and locally available packages. Linux amd64 and exact locked packages require the native GitHub Actions check. The local Docker socket remains inaccessible from this session. The workflow builds and smoke-tests the default entrypoint under offline restrictions.

## Risks and fixes

| Risk | Implemented response | Remaining limit |
|---|---|---|
| Overloaded equality changes state | Unsupported types remain unknown | Instrumentation changes allocation and timing |
| Observed ordering boundary changes behavior | Keep boundary-hit tests selected | Inputs can vary between executions |
| Comment changes source or metadata | Record file and qualified code readers | Audit events expose a subset of native and reflective observations |
| Several edits change operands | Disable operand inference across files and require one operator difference | Existing coverage fallback retains its limitations |
| Memory test observes profiling overhead | Exclude resource observers and validate economical whole tests directly | General timing-sensitive behavior remains unproved |
| Incomplete process or baseline evidence | Remove affected test from usable evidence | Unsupported process behavior may require broader profiling |
| Artifact or environment drift | Fingerprints, source verification and fallback | Target image remains unverified locally |
| Overfitting to public cases | Generic baseline maps and fresh complete-suite controls | A few controls cannot estimate hidden miss probability |

## Dead ends

The global metadata guard treated every test inspecting any code as sensitive. It increased public simulated work to 332.318 seconds. Attribution to actual files and qualified code objects resolved the excess.

The initial operand recorder classified None versus objects with default identity equality as unknown. Supporting that precise case removed unnecessary replay while preserving unknown custom equality.

Serialized code objects produced false differences from serialization details. Explicit compiled fields now identify affected code objects.

Whole-query replay still spends substantial CPU. The paired earlier runtime used about 17.3 CPU seconds. This candidate used about 4.4 CPU seconds.

## Promise

The candidate produces baseline-derived observations, retains unresolved cases through existing selection evidence, and has zero observed public misses in the measured runs.

A sub-203 organizer score, top-three finish and immunity to unseen tests remain unproven. The next organizer measurement must establish whether the local reduction transfers.

## References

Python documents identity, equality dispatch, code attributes and the audit events used here.

- https://docs.python.org/3.13/reference/datamodel.html
- https://docs.python.org/3.13/library/audit_events.html

The pinned SQLGlot checkout and official starter kit supply the source, catalog, scoring formula and constraints. The original problem page was unavailable through the web reader during this revision. The local official starter kit was reread.
