import json
import os
from pathlib import Path
import pytest
import probe

reports = {}

@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_call(item):
    __import__('sys').monitoring.restart_events()
    probe.active = item.nodeid
    os.environ['RWX_OBSERVATION_NODE'] = item.nodeid
    try:
        yield
    finally:
        probe.active = None
        os.environ.pop('RWX_OBSERVATION_NODE', None)

def pytest_runtest_logreport(report):
    reports.setdefault(report.nodeid, []).append((report.when, report.outcome))

def pytest_sessionfinish(session, exitstatus):
    out = Path(os.environ['RWX_OBSERVATION_OUT'])
    (out / 'reports.json').write_text(json.dumps(reports))
