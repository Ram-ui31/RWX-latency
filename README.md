# Current CPU-budget candidate

The default entrypoint adds budgeted verification of supported original unittest
groups. Public median selector CPU rose from about 5.02 to 11.38 seconds,
scheduled time fell from 125.574 to 113.110 seconds, and median total fell from
130.591 to 124.495 seconds, with zero public misses.

[CPU_TRADEOFF.md](CPU_TRADEOFF.md) records the measurements, rejected variants and
limits. Native Linux and organizer results are pending. Earlier candidate notes follow.

# Current candidate

The default build now adds task-aware receiver-qualified scalar settings evidence.
Its local public median is 130.591 seconds with zero misses. On three fresh settings
mutations, its median total is 15.663 seconds versus 30.959 for the prior candidate,
with zero misses. The latest organizer measurement remains 289 seconds for the
prior candidate. Native Linux and organizer validation of this revision are pending.

[DISTRIBUTION_AUDIT.md](DISTRIBUTION_AUDIT.md) explains the transfer gap, the
reused-worker attribution error, the implementation and its limits. Earlier notes follow.

# RWX Blast Radius

The default Dockerfile now builds the baseline observation candidate described in
[OBSERVATIONS.md](OBSERVATIONS.md). Its measured public median is 140.429 seconds
including local CPU with zero misses. The previous entrypoint measured 210.415
seconds on the same machine. The user reports 289 seconds on the organizer batch, versus 304 previously. See [the next-step plan](PUBLIC_REPOS_AND_NEXT_STEPS.md) for the revised target and public-entry review.

The build runs the pinned baseline tests to collect operand relations and source
metadata readers. Runtime selection combines those observations with the existing
coverage, fixture, IPC and scheduling maps. Expensive original-test verification
runs only when a baseline cost measurement justifies it.

The prior query-checkpoint candidate remains available through
`docker build -f Dockerfile.checkpoint ...`. Its earlier research notes follow.

**Experimental scoring entrypoint:** the top-level Dockerfile now builds baseline checkpoints and cost profiles and starts `run_candidate.py`. It runs calibrated whole-test verification, then restricted checkpoint execution; failures fall back to the reference path. The Docker build is **not verified locally** (daemon access denied). The original static candidate remains in `Dockerfile.reference`. Check the image build before submitting a commit. The 209.604-second combined result was a macOS research measurement, not a scored Linux container result.

**Next candidate:** see [NEXT_RUN.md](NEXT_RUN.md). Adaptive selection plus child-process evidence reproduces **234.350 simulated seconds / zero public-sample misses**, with about 1.88 seconds of local selector CPU. The organizer result for this revision is not measured.

# RWX latency: incremental validation

Source-derived test selection and worker scheduling for pinned SQLGlot.

The root runtime uses the repaired dependency map and conservative IPC serialization edges. Public sample: **250.453 simulated seconds, zero missed patches**; exported runtime equivalence is checked against the recorded output. The map combines local profiles from different dependency environments. Canonical Linux/amd64 Docker validation and unseen-change reliability remain unverified. This is not a demonstrated sub-100 result.

```bash
python3 selector.py --data-dir /path/to/data --mode hybrid
```

The default Docker entrypoint uses adaptive mode. Runtime requires only Python's standard library and no API keys. The map is derived from pinned baseline source; no sample answers or patch-answer tables are included.

`engine/` contains exact value/change and original-test validation primitives. `research/` preserves the developing evidence pipeline and tests; it requires a clean pinned SQLGlot checkout and pytest dependencies to run its capture/validation tools. Research pass-omission promotion is disabled. The root runtime uses dependency retrieval rather than unvalidated replay omissions.

See IMPLEMENTATION.md and PROPOSAL.md for design and remaining work; their research paths refer to the original development tree. This repository omits research reports and sample data. Embedded source retains SQLGlot's license in THIRD_PARTY_SQLGLOT_LICENSE.
