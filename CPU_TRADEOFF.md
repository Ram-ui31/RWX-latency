# Spend selector CPU when it removes more scheduled time

The scorer uses recorded test durations. Optimizing a local SQLGlot copy changes verification CPU. The scheduled-duration term decreases when passing tests can be omitted or the selected work can be packed better.

The accepted experiment spends additional selector CPU on supported original unittest groups.

## Programming changes

- Execute original unittest methods through a compact TestResult that records outcomes without rendering pytest tracebacks.
- Preserve unittest class fixtures, cleanup and subtest outcomes.
- Stop a group at its first failure. Keep the failing whole test and every unexecuted test selected.
- Discard omission evidence after import problems, class fixture errors, crashes, missing output and timeouts.
- Skip modules using pytest-specific APIs. The pinned source has no additional conftest fixtures for the supported scope.
- Preserve the original process implementation in any tests that invoke it.
- Reconstruct a fresh patched source tree per group, using the existing context-checked patch application.
- Keep heavy optimizer, executor, native-build, memory and subprocess-lifecycle tests outside this experimental group scope.
- Try an action only when its optimistic marginal schedule saving exceeds its estimated execution cost. The estimate guides work, while observed completion authorizes omission.
- Limit the additional stage to a soft 20 CPU-second budget, an approximately 100-second wall window, and an eight-second wall timeout per action.

The cost estimate uses 0.8 seconds of startup plus 0.1 times recorded candidate durations. This is an experimental scheduling estimate, not a calibrated upper bound. One in-flight action can overshoot the soft CPU budget. Unknown hidden edits can make verification uneconomical.

The existing baseline-observation and settings stages still run first. Their passing-test observations are preserved. Failed additional verification retains the upstream selection.

## Complete public runs

All three runs used the actual entrypoint and included child-process CPU.

| Run | Simulated seconds | CPU seconds | Total seconds | Missed patches |
|---|---:|---:|---:|---:|
| 1 | 113.110 | 11.213596 | 124.323596 | 0 |
| 2 | 113.110 | 11.761294 | 124.871294 | 0 |
| 3 | 113.110 | 11.384913 | 124.494913 | 0 |

The prior candidate measured 125.574 simulated seconds and 130.591220 median total seconds. The new median total is 124.494913 seconds, approximately 4.67 percent lower.

The scheduled-duration reduction is 12.464 seconds. Additional median CPU is approximately 6.368 seconds. The net measured reduction is approximately 6.096 seconds.

These are ARM macOS public-sample measurements. Native Linux and organizer results remain pending. The latest organizer result is 289 seconds for an earlier candidate.

## Rejected variants

Broad minimal verification reduced scheduled time but spent almost as much CPU as it saved.

Preloading external dependencies and forking a warm process performed worse locally. One run consumed 33.160029 additional CPU seconds for 19.254 scheduled seconds saved. This variant is implemented only as an explicit research flag and is absent from the default invocation.

The prior broad pytest-group verifier consumed 35.615562 CPU seconds to remove 0.428 simulated seconds. It remains outside the default invocation.

The selected scope excludes the expensive optimizer fixture class and verifies cheaper methods. Its separately measured additional stage used 6.431648 CPU seconds to remove 12.464 scheduled seconds.

## Checks

The minimal runner completed all 1,387 supported baseline methods successfully. All 41 repository regression checks passed.

New regression checks cover successful subtests continuing through the suite, a failing subtest retaining the parent and unexecuted tests, class teardown failure invalidating pass evidence, and skips remaining unresolved.

The three previously independently labeled settings controls still had zero misses. The additional budget policy chose no verification actions on them, so they do not provide new failure-equivalence evidence for this runner.

The public sample exercises passing groups and first-failure retention. Larger untouched mutation groups and native organizer measurements are needed to assess transfer.

## Next programming work

Baseline cost profiles should replace the rough scheduling estimate before expanding the supported scope. The next expensive targets need case-level obligations or cheaper complete execution, including lifecycle and assertions. Raising the budget alone does not create a net saving.
