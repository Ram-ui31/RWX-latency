# Optimizer fixture adapter: shadow implementation

The adapter in `engine/fixture_adapter.py` runs only changed fixture records
through the original pinned `TestOptimizer.check_file` helper and its original
assertions. The optional adapter argument in `engine/runner.py` leaves normal
whole-test execution unchanged. The competition selector does not activate it.

The planner permits one existing optimizer SQL fixture edit and one unambiguous
test method consisting of one `self.check_file` invocation. It preserves new
queries, expectations, schemas/options passed by the original method, dialect
metadata, original subtest titles and record positions. Reader helper changes,
source/multi-file edits, record-count changes, pure reordering, ambiguous bodies,
native execution metadata and malformed patches are rejected. Unknown evidence
never becomes a pass. Exact visited-record accounting detects skipped replay.

## Execute the shadow harness

From this repository, in an environment with pytest 9, pytest-timeout, DuckDB,
pandas and the pinned SQLGlot checkout:

```bash
python research/fixture_adapter/shadow.py \
  --source /path/to/clean/pinned/sqlglot \
  --data /path/to/data \
  --output /tmp/shadow-report.json \
  --cpu-budget 180 --timeout 30
python -m unittest discover -s tests -v
```

The harness verifies clean pinned Git source, checks the baseline whole test,
then compares patched whole-test execution with filtered original-pool and
filtered single-worker execution. It does not read sample answers. Parent and
child CPU are measured; source-copy/setup costs are included. The evaluation
budget stops new cases, while individual action timeout limits bound ongoing
work; it is not a hard process-tree CPU quota. Timeout/error/skip/incomplete
execution produces unresolved evidence. A zero budget executes no replay.

## Measured results

Four eligible public fixture patches and three newly generated cases were
executed. All seven matched original whole-test outcomes in both replay
configurations: **14 outcome comparisons, no disagreements**. The generated
cases cover a title-only passing change, a wrong expected output and two wrong
expected outputs in one test. They are from the same fixture family, not an
independent source-region or mechanism-complete holdout.

The passing case's single-worker action used **1.173 CPU seconds including
parent preparation** against **2.083 seconds of possible marginal scheduling
saving**, leaving about **0.910 seconds** of potential net saving. The six
failing cases must remain selected: they offer **zero omission savings**, and
verification would add CPU. Positive optimistic figures in research reports
are upper bounds assuming omission, not savings earned by a failing case.

Ten targeted tests pass, including the five earlier selection/IPC tests.
The selector's emitted public output is byte-for-byte unchanged and still
scores **234.350 simulated seconds / zero misses**. This adapter has not improved
the competition score. Canonical Docker equivalence remains unverified.

## Promotion status

**Shadow only; omissions disabled.** Original helper reuse does not by itself
prove that all records are independent. Shared mutable schemas, optimizer
caches, ordering, process state and unchanged-record interactions require more
validation or a stricter eligibility contract. The independent challenges do
not cover all of these risks. A single passing case is insufficient economics
or reliability evidence for promotion.

Next: expand independently specified challenges to state/metadata/control-flow
boundaries, compare full-suite retrieval periodically, and gather net-benefit
measurements on material critical-path cases. Keep native executor replay out
of this adapter. Retain the current selector when any evidence is missing.
