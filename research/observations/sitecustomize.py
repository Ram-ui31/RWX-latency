"""Install the same baseline operand recorder in spawned Python workers."""
import atexit
import json
import os
from pathlib import Path

if 'RWX_OBSERVATION_OUT' in os.environ:
    import probe
    out = Path(os.environ['RWX_OBSERVATION_OUT'])
    (out / f'start-{os.getpid()}.json').write_text(json.dumps(os.environ.get('RWX_OBSERVATION_NODE','')))
    probe.install(os.environ['RWX_OBSERVATION_SOURCE'])
    def flush():
        out = Path(os.environ['RWX_OBSERVATION_OUT'])
        (out / f'process-{os.getpid()}.json').write_text(json.dumps(probe.values))
    atexit.register(flush)
