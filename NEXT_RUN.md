# Next run: v3 (slow-test evidence, signature defaults, faster selection)

22 November 2026. Board history for this repository (practice set, 40 commits):

| Commit | Simulated | CPU | Total |
|---|---:|---:|---:|
| fc160… | 290.4 | 13.8 | 304.2 |
| 478f2… | 280.5 | 9.0 | 289.5 |
| 7cdb41b | 251.8 / 255.5 | 19.4 / 26.7 | 271.2 / 282.3 |

The same commit scored 271.2 and 282.3: time-limited verification makes runs drift.

## Evaluation data

Public competitor corpora were re-batched into 40-commit runs (evaluation only, never in
the image). `corpus/v1` (buidangnguyen05) reproduces the organizer's 30 sample answers and
uses only the organizer's kinds; it is the closest stand-in for the practice set. The old
default scores ~337 per 40 commits there (sim + CPU) against a 118 oracle.

## Changes (v2 → v3)

1. **Comment/docstring reduction** (`engine/reduce.py`), **isolated coverage**
   (`maps/isolated-coverage.json.gz`, `engine/isosel.py`, `engine/astdiff.py`) and the
   **TPC differential guard** (`research/tpcds_guard/`), as in v2.
2. **Signature defaults**: a def whose only change is a constant default value (with lazy
   annotations) is a call-time edit: tests that entered the function, not every importer.
   Organizer-style `copy: bool = True → False` edits drop from 700–1,100 tests to callers.
3. **TPC-DS execution check**: when parse/optimize/plan outputs change for a few queries,
   the original subtests of exactly those queries are executed with the patched code; every
   other query is unchanged. Bounded by the expected saving.
4. **Slow-test evidence** (`research/infer/`), after selection:
   * `test_max_nodes`: a 1.5 s differential check (`maxnodes.py`) runs every cheap assertion
     and compares trees and full error messages on a periodic prefix that reaches the same
     node limit at the same position;
   * `test_generator_memory`: run on its own (2 s) when it decides the schedule;
   * when every other runnable candidate passes on the patched tree, the remaining slow
     tests (TPC-DS/TPC-H execution, max nodes, generator memory, scope) are omitted. In
     1,259 labelled commits these six never failed without a cheaper test failing too.
     This is an empirical rule, not a proof; it is the only non-evidence omission.
5. **CPU**: AST comparison keyed by source text (3× faster, identical results on 1,452
   edits), cached parsing, a quadratic scan removed from typed-settings narrowing. Stage-1
   selection fell from ~14 to ~7 CPU seconds per 40 commits.
6. A batch deadline (4.5 s per commit) gates the later stages.

## Measured locally (Linux, Python 3.13.18, locked packages, 2 CPUs; sim + CPU per 40)

| Configuration | v1 corpus | Public sample (30) | Misses |
|---|---:|---:|---:|
| Old default (7cdb41b) | ~337 | 127 | 2 (v1) |
| v2 (81dc0cf) | ~296 | 122.5 | 0 |
| v3 | ~267 | 124.0 | 0 |

On v1 the remaining excess is mostly commits where TPC-DS stays selected next to a real
cheap failure, and very wide selections (tokenizer/parser core edits).
