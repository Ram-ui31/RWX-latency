import hook, os, pytest, json
from pathlib import Path

reports = {}


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_call(item):
    hook.active = item.nodeid
    os.environ["RWX_TYPED_NODE"] = item.nodeid
    try:
        yield
    finally:
        hook.active = None
        os.environ.pop("RWX_TYPED_NODE", None)


def pytest_runtest_logreport(report):
    reports.setdefault(report.nodeid, []).append([report.when, report.outcome])


def pytest_sessionfinish(session, exitstatus):
    Path(os.environ["RWX_TYPED_OUT"], "reports.json").write_text(json.dumps(reports))
