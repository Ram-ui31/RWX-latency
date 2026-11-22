"""Run original unittest methods in one interpreter and report each outcome.

Same execution as research/group_verifier/minimal.py (unittest semantics, class
fixtures, subtests, real process pools), with an optional non-failfast mode so
passing tests can be pruned even when another candidate fails.
"""
import argparse
import importlib
import json
import resource
import sys
import time
import unittest
from pathlib import Path


def cpu():
    used = resource.getrusage(resource.RUSAGE_CHILDREN)
    return time.process_time() + used.ru_utime + used.ru_stime


class Outcomes(unittest.TestResult):
    def __init__(self, failfast):
        super().__init__()
        self.status = {}
        self.costs = {}
        self.lifecycle_error = False
        self.failfast = failfast

    def startTest(self, test):
        super().startTest(test)
        self.status[test.id()] = 'running'
        self.started = cpu()

    def stopTest(self, test):
        self.costs[test.id()] = cpu() - self.started
        super().stopTest(test)

    def addSuccess(self, test):
        if self.status.get(test.id()) == 'running':
            self.status[test.id()] = 'pass'

    def _fail(self, test):
        self.status[test.id()] = 'fail'
        if self.failfast:
            self.stop()

    def addFailure(self, test, err):
        self._fail(test)

    def addError(self, test, err):
        if not isinstance(test, unittest.TestCase):
            self.lifecycle_error = True
            if self.failfast:
                self.stop()
            return
        self._fail(test)

    def addSubTest(self, test, subtest, err):
        if err is not None:
            self._fail(test)

    def addSkip(self, test, reason):
        self.status[test.id()] = 'unknown'

    def addExpectedFailure(self, test, err):
        self.status[test.id()] = 'unknown'

    def addUnexpectedSuccess(self, test):
        self.status[test.id()] = 'unknown'


def execute(source, requested, output, failfast):
    started = cpu()
    sys.path.insert(0, str(Path(source).resolve()))
    suite = unittest.TestSuite()
    names = {}
    load_error = []
    for node in requested:
        path, cls, method = node.split('::')
        try:
            module = importlib.import_module(path.removesuffix('.py').replace('/', '.'))
            case = getattr(module, cls)
            test = case(method)
            names[test.id()] = node
            suite.addTest(test)
        except Exception as ex:  # an import failure fails the file's tests
            load_error.append([node, type(ex).__name__])
            if failfast:
                break
    result = Outcomes(failfast)
    if not (load_error and failfast):
        suite.run(result)
    status = {names[n]: s for n, s in result.status.items() if n in names}
    for node, _ in load_error:
        status[node] = 'fail'
    output.write_text(json.dumps({
        'status': status,
        'lifecycle_error': result.lifecycle_error,
        'load_error': load_error,
        'costs': {names[n]: v for n, v in result.costs.items() if n in names},
        'total_cpu': cpu() - started,
    }))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--nodes', type=Path, required=True)
    p.add_argument('--result', type=Path, required=True)
    p.add_argument('--failfast', action='store_true')
    a = p.parse_args()
    execute(a.source, json.loads(a.nodes.read_text()), a.result, a.failfast)


if __name__ == '__main__':
    main()
