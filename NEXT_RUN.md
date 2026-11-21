# Next run: mixed granularity and child-process evidence

21 November 2026. The user reports **324 seconds** on the organizer set. That total does not identify simulation, CPU, or missed-patch components. It is not directly comparable with the smaller public sample.

## Implemented

1. Profile the original pinned lazy-import test's child interpreter. Merge actual function-entry and module-import evidence into the source map. Record its statement coverage as incomplete. This resolves the last always-selected untrusted test; it does not claim support for arbitrary subprocesses.
2. Use statement/reader selection for supported body and fixture edits. Use the existing broader module/class policy for initialization changes. Invalid context, source observers and unsupported changes retain conservative fallbacks.
3. Extend serialization closure through local helpers, explicit imported helpers, module aliases and aliases to process-pool classes. Union ambiguous import aliases instead of silently taking the last one. Keep these extra consumers additive.
4. Handle malformed patches as full-selection fallbacks instead of rejecting the entire runtime batch.

No outcome-trained weights, patch hashes, or edit-kind-to-failure tables are used. All new map evidence comes from the pinned baseline. Live replay omissions remain disabled.

## Research basis

- [Ekstazi, ISSTA 2015](https://mir.cs.illinois.edu/~marinov/publications/GligoricETAL15PracticalRTS.pdf): dynamic file dependencies and end-to-end measurement. Applied here by accounting for analysis CPU and retaining raw file/fixture dependencies.
- [STARTS, ASE 2017](https://mir.cs.illinois.edu/awshi2/publications/ASEDEMO2017.pdf): transitive static dependencies. Applied here to process serialization helpers.
- [NameRTS, 2026 preprint](https://arxiv.org/html/2605.25356v1): Python name/element dependencies, import-time behavior and context-aware pruning. Motivated the initialization guard experiment and alias handling. This implementation is not NameRTS. Its published empirical safety is not a guarantee for RWX.

## Controlled comparisons on the 30 inspected public patches

| Policy | Simulated seconds | Missed patches | Decision |
|---|---:|---:|---|
| Previous submitted-code local reproduction | 250.453 | 0 | Reference |
| Blanket fine-grained impact mode | 483.425 | 0 | Reject: initialization falls back too broadly |
| Adaptive granularity + child trace | 234.350 | 0 | Keep |
| Adaptive + unpruned name closure | 380.646 | 0 | Reject: dependency cascades and extra analysis cost |
| Adaptive + deeper serialization closure | 234.350 | 0 | Next candidate |

Final local selector CPU: **1.878996 seconds**; local sum approximately **236.229 seconds**. This is not an official container score or three-run median. Previous and current evidence were collected on macOS under different dependency versions; the map explicitly records that provenance. Canonical Docker validation remains outstanding.

## Verification and limits

Five new targeted tests cover transitive helper/alias propagation, ambiguous alias union, initialization fallback, unknown evidence and valid empty certificates. The existing core suite was rerun. Label-free metamorphic checks pass under reversed catalog numbering and renamed patch IDs for all 30 patches; malformed input produces a valid full-selection result.

The public cases are already inspected. These results do not establish unseen-change recall or predict an organizer score below 324. Arbitrary reflection, eval, native boundaries and unobserved dynamic dispatch remain limitations. The unpruned name experiment is retained under research as a rejected approach; no negative reachability claim from it is used to remove tests.

## Run and publish

The Docker default is now `adaptive`. Local reproduction:

```bash
python3 selector.py --mode adaptive --data-dir /path/to/data
python3 -m unittest discover -s tests -v
```

The repository contains no sample patches, answers, credentials or local diagnostic logs. Do not add external development data when committing. The research child profiler expects the original development layout; its output map is already frozen at `maps/source-index.json.gz`.
