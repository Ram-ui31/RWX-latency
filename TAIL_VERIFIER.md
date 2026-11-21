# Analysis and next implementation: calibrated, cost-first verification

## What went wrong

The optimizer-fixture adapter optimized the easiest integration point rather than the dominant costs. Only four public patches were eligible, and those four still failed their original tests, so verifying them could not justify omission. The one generated passing case saved about 0.91 seconds. Agreement on seven cases was useful correctness evidence but poor evidence of a substantial speedup.

Five expensive public selections account for about 130.6 of the current 234.35 simulated seconds. They contain TPC-DS execution; other expensive selections contain generator-memory testing. Whole-test duration, marginal schedule saving, verification wall time and verification CPU are different quantities.

The first tail experiment also failed: five uncalibrated actions incurred 18.162 CPU seconds, four timed out at eight wall seconds, and one confirmed a real failure. No test could be removed. Its local total worsened to 252.512 seconds. Raising the deadline allowed the TPC-DS check to pass, but that action used 28.262 CPU seconds to save at most 21.454 scheduled seconds. Longer timeouts alone do not fix the economics.

## Implemented change

`research/tail_verifier/calibrate.py` measures original tests against a clean pinned baseline, without accepting patches or answers. It stores interpreter/platform/package identity, baseline status and measured action CPU. These measurements are not failure predictions or hard cost bounds.

`engine/verification_budget.py` rejects missing, invalid, unaffordable and uneconomical cost evidence. It uses a 25% margin plus 0.25 seconds of overhead. This margin is a starting engineering assumption, not a calibrated statistical guarantee. Environment mismatches invalidate the cost profile.

`research/tail_verifier/evaluate.py` chooses actions by marginal scheduled cost, executes original whole tests in independent patched source trees, and charges analysis, preparation and child CPU. Passing observations can remove tests only from the experimental output; failure/timeout/error evidence retains them. The competition selector does not invoke this experiment. A failed cost gate does not prevent the controller examining other candidates. Failed or uneconomical actions stop additional work in that patch for this evaluation.

Unknown costs do not authorize a run by default. An explicitly named uncalibrated-experiment option remains for reproducing the failed initial trial. It must not be used as the deployment policy. Evaluation CPU budgets are soft; a running process-tree action can exceed them. Deadlines kill the process group and unresolved tests remain selected.

## Measured outcome

Baseline calibration in this local environment:

| Original test | Baseline CPU including preparation | Decision |
|---|---:|---|
| TPC-DS executor | 27.986 s | Reject whole-test replay at current marginal savings |
| Generator memory | 1.094 s | Evaluate only when marginal savings exceed estimated CPU |

The gated public experiment verified four generator-memory tests. All passed in their respective patched trees. It avoided the expensive executor actions.

| Quantity | Result |
|---|---:|
| Experimental simulated seconds | 214.592 |
| Public missed patches | 0 |
| Measured evaluation CPU | 5.843015 s |
| Local combined total | 220.435015 s |
| Reference simulated seconds | 234.350 |

The experiment removed 19.758 scheduled seconds and spent 5.843 CPU seconds. Compare the combined result with the reference's own analysis CPU, not simulation alone. This is a single local measurement, not an official three-run median. The user-reported 324-second organizer result is a different workload with unknown breakdown.

A separate generated challenge introduced an allocation leak into the original generator constructor. The verifier observed the resource-test failure and retained the test. A harmless constructor comment control passed. These two controls use a one-test catalog to isolate verifier behavior, so they do not establish full-suite recall or private-set generalization. Sixteen targeted tests pass, including cost validation and marginal-priority controls.

## Reproduce

From this repository, with pytest 9, pytest-timeout, DuckDB, pandas and a clean pinned SQLGlot checkout available:

```bash
python research/tail_verifier/calibrate.py \
  --source /path/to/sqlglot --catalog /path/to/data/tests.json \
  --numbers 1106 1224 --output /tmp/baseline-costs.json

python research/tail_verifier/evaluate.py \
  --source /path/to/sqlglot --data /path/to/data \
  --cost-profile /tmp/baseline-costs.json \
  --report /tmp/tail-report.json --predictions /tmp/tail-predictions.jsonl \
  --cpu-budget 20 --action-timeout 8 --min-saving 2 --max-actions 5
```

The listed numbers refer to the current official catalog. Costs are stored and joined by full test identity; use the appropriate numbers for a different catalog. The output is research counterfactual selection, not an approved submission. The CLI never reads answers; only offline scoring does.

## Next plan and promotion gates

1. Keep the current selector recoverable. Freeze the measured candidate and cost provenance.
2. Repeat cost calibration and outcome checks inside the exact organizer image and limits. Local memory/resource behavior and mixed source maps do not establish canonical equivalence.
3. Test independent edits that genuinely break the verified tests, plus import, setup, timeout and multi-failure cases. Whole-suite checks must audit failures outside the retrieved shortlist.
4. Integrate optional verification only when both semantics and net benefit are supported in that environment. Profile mismatches, unknowns and budget exhaustion must retain the reference selection.
5. For the expensive executor bottleneck, stop rerunning the whole test. Investigate reusable pure optimizer/executor-stage boundaries with exact input and state contracts. Require baseline completeness and differential validity before any omission; the prior fixture adapter is a correctness control, not a shortcut around those gates.

No under-100 or top-three result follows. The key finding is that different expensive tests need different strategies: some are cheap to verify locally, while others require avoiding repeated computation. A single blanket replay architecture wastes CPU.
