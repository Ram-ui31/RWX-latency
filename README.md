# RWX latency: incremental validation

Source-derived test selection and worker scheduling for pinned SQLGlot.

The root runtime uses the repaired dependency map and conservative IPC serialization edges. Public sample: **250.453 simulated seconds, zero missed patches**; exported runtime equivalence is checked against the recorded output. The map combines local profiles from different dependency environments. Canonical Linux/amd64 Docker validation and unseen-change reliability remain unverified. This is not a demonstrated sub-100 result.

```bash
python3 selector.py --data-dir /path/to/data --mode hybrid
```

The default Docker entrypoint uses hybrid mode. Runtime requires only Python's standard library and no API keys. The map is derived from pinned baseline source; no sample answers or patch-answer tables are included.

`engine/` contains exact value/change and original-test validation primitives. `research/` preserves the developing evidence pipeline and tests; it requires a clean pinned SQLGlot checkout and pytest dependencies to run its capture/validation tools. Research pass-omission promotion is disabled. The root runtime uses dependency retrieval rather than unvalidated replay omissions.

See IMPLEMENTATION.md and PROPOSAL.md for design and remaining work; their research paths refer to the original development tree. This repository omits research reports and sample data. Embedded source retains SQLGlot's license in THIRD_PARTY_SQLGLOT_LICENSE.
