# Baseline observation provenance

These are unchanged baseline-only artifacts exported by native Linux amd64 workflow
[44959722803](https://github.com/Ram-ui31/RWX-latency/actions/runs/44959722803),
from commit `748e3fd83217bad62d6384ba1d9f9a1c0389ec06`.

Source: SQLGlot `eb11aec4be8cb2122afe713a4816662c3f0fb2fa`.
The complete original baseline passed 1,620 tests and 25,440 subtests.
The maps record comparison/source observers, receiver-qualified reads and validation
states, and compiled argument propagation. They contain no mutation outcomes or
patch-answer lookup table.

The default build checks source hashes, source-index identity, Python/package/platform
identity, task attribution and the binding between these artifacts. CPU cost profiles
are freshly measured during each build. The baseline maps can be regenerated using
`Dockerfile.rebuild-maps`; its tracing/build scripts remain in `research/`.
