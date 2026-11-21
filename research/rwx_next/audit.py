#!/usr/bin/env python3
"""OFFLINE diagnosis. Reads public answers; never package into a selector image.

No predictor or runtime map is produced. Feature-class oracle expansion below
is an impossibility diagnostic for deterministic rowwise classifiers only.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'rwx'))
from blast.catalog import load_catalog
from blast.selection import SourceIndex
from blast.scheduling import optimize_schedule, schedule_cost


def lower_bound(numbers, durations):
    """Valid integer-ms scheduling lower bound, independent of the heuristic."""
    if not numbers:
        return 0
    total = sum(durations[n] for n in numbers)
    largest = max(durations[n] for n in numbers)
    return min(max(largest, (total + k - 1) // k) + 2000 * k
               for k in range(1, min(8, len(numbers)) + 1))


def feature_audit(path, answers, durations):
    groups = {}
    with gzip.open(path, 'rt') as f:
        header = json.loads(next(f))
        rows = 0
        for line in f:
            row = json.loads(line)
            # Canonical numeric JSON avoids treating 0 and 0.0 as different.
            key = tuple(None if x is None else float(x) for x in row['x'])
            groups.setdefault(key, []).append((row['change'], row['number']))
            rows += 1
    mixed = []
    forced = {c: set() for c in answers}
    for members in groups.values():
        positives = [(c, n) for c, n in members if n in answers[c]['failing']]
        negatives = [(c, n) for c, n in members if n not in answers[c]['failing']]
        if positives and negatives:
            mixed.append((len(positives), len(negatives)))
        if positives:
            for c, n in members:
                forced[c].add(n)
    lb = sum(lower_bound(ns, durations) for ns in forced.values())
    feasible = sum(schedule_cost(optimize_schedule(ns, durations), durations)
                   for ns in forced.values())
    return dict(
        source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        rows=rows, predictors=len(header['predictor_names']),
        distinct_numeric_vectors=len(groups), contradictory_groups=len(mixed),
        positives_in_contradictory_groups=sum(a for a, _ in mixed),
        negatives_in_contradictory_groups=sum(b for _, b in mixed),
        zero_miss_rowwise_feature_class_scheduling_lower_bound_seconds=lb / 1000,
        oracle_expansion_feasible_schedule_seconds=feasible / 1000,
        bound_attained=(lb == feasible),
        scope='Same numeric vector must receive same binary decision; no live evidence, joint context or other inputs. Offline labels supply the optimal feature-class oracle. Not an achievable trained-model result.',
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, default=ROOT / 'rwx_next/reports/core_audit.json')
    args = ap.parse_args()
    tests, ids, durations = load_catalog(ROOT / 'rwx/sample/sample/tests.json')
    answers = json.loads((ROOT / 'rwx/sample/sample/answers.json').read_text())['commits']
    ix = SourceIndex(ROOT / 'rwx/maps/impact-index-v5.json.gz', ids)
    legacy = json.loads((ROOT / 'rwx/reports/hybrid-v5.json').read_text())
    manifest = json.loads((ROOT / 'rwx_signals/artifacts/round2_manifest.json').read_text())
    oracle_sets = [set(a['failing']) for a in answers.values()]
    oracle_lb = sum(lower_bound(ns, durations) for ns in oracle_sets)
    oracle_cost = sum(schedule_cost(optimize_schedule(ns, durations), durations) for ns in oracle_sets)
    uncertain = sorted(ix.unobserved, key=lambda n: (-durations[n], n))
    positive_pairs = [n for answer in answers.values() for n in answer['failing']]
    policies = {}
    for protocol, models in manifest['protocols'].items():
        policies[protocol] = {}
        for name, result in models.items():
            p = result['calibrated_policy']
            penalty = 300 * p['missed_changes']
            policies[protocol][name] = dict(
                simulation=p['simulated_seconds'], misses=p['missed_changes'],
                penalty_seconds=penalty,
                selected_work_seconds=round(p['simulated_seconds'] - penalty, 3))
    result = dict(
        status='offline_diagnostic_not_submission', labels_read=True,
        public_changes=len(answers), catalog_tests=len(tests),
        public_failure_distribution=dict(
            positive_pairs=len(positive_pairs),
            unique_failing_tests=len(set(positive_pairs)),
            positive_pairs_in_untrusted_region=sum(n in ix.unobserved for n in positive_pairs),
            unique_failing_tests_in_untrusted_region=len(set(positive_pairs) & ix.unobserved),
            positive_pairs_by_test_file=dict(Counter(tests[n]['file'] for n in positive_pairs))),
        legacy=dict(simulated_seconds=legacy['simulated_ms'] / 1000,
                    misses=legacy['misses'],
                    per_patch_cost_counts=dict(Counter(str(x['base_ms'] / 1000) for x in legacy['details']))),
        uncertainty=dict(count=len(uncertain),
                         forced_every_patch_lower_bound_seconds=len(answers) * (durations[uncertain[0]] + 2000) / 1000,
                         top_tests=[dict(number=n, test=tests[n]['id'], seconds=durations[n] / 1000) for n in uncertain[:12]]),
        public_oracle=dict(scheduling_lower_bound_seconds=oracle_lb / 1000,
                           feasible_schedule_seconds=oracle_cost / 1000,
                           bound_attained=(oracle_lb == oracle_cost),
                           cpu_margin_to_100_seconds=(100000 - oracle_cost) / 1000),
        feature_audits={name: feature_audit(ROOT / f'rwx_signals/artifacts/{name}.jsonl.gz', answers, durations)
                        for name in ('public-signals-v2', 'public-signals-rich-v2')},
        learned_policy_decomposition=policies,
        canonical_container_run=False,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'learned_policy_decomposition'}, indent=2))


if __name__ == '__main__':
    main()
