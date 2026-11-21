#!/usr/bin/env python3
"""OFFLINE only: compare frozen smoke observations with public answers."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    report = ROOT / 'rwx_next/reports/replay_smoke.json'
    smoke = json.loads(report.read_text())
    answers = json.loads((ROOT / 'rwx/sample/sample/answers.json').read_text())['commits']
    eligible = set(smoke['eligible_numbers'])
    expected = sum(len(set(a['failing']) & eligible) for a in answers.values())
    false_failures, unobserved = [], []
    for c, observation in smoke['patches'].items():
        actual = set(answers[c]['failing']) & eligible
        observed = set(observation.get('observed_failures', []))
        false_failures.extend([c, n] for n in sorted(observed - actual))
        unobserved.extend([c, n] for n in sorted(actual - observed))
    result = dict(
        status='offline_comparison_not_competitive_result', labels_read=True,
        eligible_tests=len(eligible), public_positive_pairs_in_eligible_subset=expected,
        patched_tests_run=sum(r.get('tests_run', 0) for r in smoke['patches'].values()),
        patches_executed=sum(r.get('requested', 0) > 0 for r in smoke['patches'].values()),
        unsupported_patches=sum(r.get('status') == 'unsupported' for r in smoke['patches'].values()),
        false_observed_failures=false_failures, eligible_failures_not_observed=unobserved,
        unknown_observations=sum(len(r.get('unknown', [])) for r in smoke['patches'].values()),
        patch_child_cpu_seconds=smoke['patch_child_cpu_seconds'],
        conclusion='No positive cases in this subset: no failure-recall evidence. Simple SQL replay does not address the expensive or failure-dense missing regions. Do not promote.',
        canonical=False,
    )
    output = ROOT / 'rwx_next/reports/replay_comparison.json'
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
