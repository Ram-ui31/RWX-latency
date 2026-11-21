"""Run original unittest groups without rendering assertion tracebacks."""

import argparse
import importlib
import json
import os
from pathlib import Path
import sys
import unittest
import resource
import time


def cpu():
    used = resource.getrusage(resource.RUSAGE_CHILDREN)
    return time.process_time() + used.ru_utime + used.ru_stime


class Outcomes(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.status = {}
        self.lifecycle_error = False
        self.costs = {}
        # Stop at the first failure and retain every unexecuted test.
        self.failfast = True

    def startTest(self, test):
        super().startTest(test)
        self.status[test.id()] = "running"
        self.started = cpu()

    def stopTest(self, test):
        self.costs[test.id()] = cpu() - self.started
        super().stopTest(test)

    def addSuccess(self, test):
        if self.status.get(test.id()) == "running":
            self.status[test.id()] = "pass"

    def addFailure(self, test, err):
        self.status[test.id()] = "fail"
        self.stop()

    def addError(self, test, err):
        self.status[test.id()] = "fail"
        self.stop()
        if not isinstance(test, unittest.TestCase):
            self.lifecycle_error = True

    def addSubTest(self, test, subtest, err):
        if err is not None:
            self.status[test.id()] = "fail"
            self.stop()

    def addSkip(self, test, reason):
        self.status[test.id()] = "unknown"

    def addExpectedFailure(self, test, err):
        self.status[test.id()] = "unknown"

    def addUnexpectedSuccess(self, test):
        self.status[test.id()] = "unknown"


def execute(source, requested, output):
    started = cpu()
    sys.path.insert(0, str(source.resolve()))
    suite = unittest.TestSuite()
    names = {}
    load_error = False
    for node in requested:
        parts = node.split("::")
        if len(parts) != 3:
            continue
        path, cls, method = parts
        module_name = path.removesuffix(".py").replace("/", ".")
        try:
            # Pytest-specific modules retain their ordinary selection.
            module_source = (source / path).read_text()
            if "pytest" in module_source:
                continue
            module = importlib.import_module(module_name)
            case = getattr(module, cls)
            if not isinstance(case, type) or not issubclass(case, unittest.TestCase):
                continue
            test = case(method)
            names[test.id()] = node
            suite.addTest(test)
        except Exception:
            load_error = True
            continue
    result = Outcomes()
    suite.run(result)
    passed = (
        []
        if result.lifecycle_error or load_error
        else [
            names[name]
            for name, status in result.status.items()
            if status == "pass" and name in names
        ]
    )
    total = cpu() - started
    costs = {names[n]: v for n, v in result.costs.items() if n in names}
    output.write_text(
        json.dumps(
            {
                "passed": passed,
                "lifecycle_error": result.lifecycle_error,
                "costs": costs,
                "total_cpu": total,
                "overhead_cpu": max(0, total - sum(costs.values())),
            }
        )
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--nodes", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    execute(args.source, json.loads(args.nodes.read_text()), args.result)


if __name__ == "__main__":
    main()
