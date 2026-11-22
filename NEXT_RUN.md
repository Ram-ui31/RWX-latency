# Next run: isolated coverage, docstring/comment reduction, TPC guard

22 November 2026. The organizer reported about 270–289 seconds (0 misses) while the public
sample scored about 110–127. The public sample is not representative: on 637 independently
labeled mutations in the organizer's style (public competitor corpora, re-batched into
40-commit runs), the previous default scored a median of ~590 simulated seconds per 40
commits and missed 8 commits (1.3% of commits, 300 s each).

## What was wrong

| Cause | Share of excess (per 40 commits, previous default) |
|---|---:|
| Docstring/comment edits fell back to all 1,620 tests (36.8 s each) | ~87 |
| Shared-process coverage attributed import-time work, caches and lazy imports to the first test only, so body edits either fell back to all tests or **missed** failures (import-time helpers, parser code run while importing, broken imports) | ~90 + most misses |
| TPC-DS (21.5 s) kept for optimizer/parser/fixture edits that cannot change its result | ~88 |

## Implemented (default image)

1. `engine/reduce.py` drops Python hunks whose docstring-normalized AST is unchanged
   (comments, whitespace, docstrings). Tests that read the file as data are kept.
2. `maps/isolated-coverage.json.gz` + `engine/isosel.py`: every catalog test traced alone
   (base import / test module / single test, spawned interpreters included; all 1,620
   passed). `engine/astdiff.py` classifies each Python edit:
   * body edits → tests that executed the edited statements, changed headers, insertion
     neighbours, or entered an edited lambda;
   * structural import-time edits (imports, defs, signatures, syntax errors) → every
     isolated importer of the module;
   * same-target value assignments (class settings, dict entries) → unchanged receiver/
     key-sensitive selector (isolated importers were measured to cost more than its
     residual misses);
   * fixtures/new/deleted files → unchanged selector.
   Baseline operand evidence (single `is`/`<`/`>` substitutions) still removes tests whose
   recorded operands cannot change the comparison.
3. `research/tpcds_guard/`: at build, record per-query canonical outputs of the stages the
   executor tests recompute (parse, DuckDB transpile, optimize, plan) and every SQLGlot
   line the rest of the test executes. At run time, when no edited line or edited setting
   name is in that "outside" set, recompute only the queries whose traced lines intersect
   the edit; identical outputs remove `test_execute_tpcds`/`test_execute_tpch`/
   `test_optimized_tpch`. TPC-H fixture edits are checked by loading the fixture with the
   original loader. Same-target value edits (class settings, dict entries) are eligible
   when no outside line reads that name: plain assignments to the same name elsewhere are
   writes, `__dict__.get("NAME")`-style reads count as reads of NAME, and a short list of
   reviewed computed-name reads (`*_sql` dispatch tables, instance attributes, module
   lookups) cannot read an upper-case class setting.

## Measured (local Linux, Python 3.13.18, locked packages, 2 CPUs)

| Run | Public sample sim | Corpus sim / 40 (organizer kinds) | Corpus misses |
|---|---:|---:|---:|
| Previous default | 109.4 | 529 | 8 |
| + reduction | 109.0 | 453 | 8 |
| + isolated coverage + operand evidence + TPC guard | 106.9 | 311 | 2 |

The two remaining misses are value edits in widely imported dialect classes (Hive
`ALIAS_POST_TABLESAMPLE`, Spark2 tokenizer `KEYWORDS`), still on the old selector. On those
corpora the guard never removed a TPC test that actually failed (0 of 46 checks unsafe).
The corpora are public competitor-generated mutations; they are evaluation data only and
are not in the image.

## Remaining opportunity (per 40 commits on the corpus)

* value edits on the old selector: ~60 excess + residual misses;
* body edits: ~33; structural import-time edits: ~26;
* frequently over-selected heavy tests: annotate_funcs, generator_memory, TPC-DS.
