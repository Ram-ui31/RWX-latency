"""Boundary checks for argument-value omission and conservative observers."""

import hashlib
from types import SimpleNamespace
import unittest

from research.state_diff.choose import ArgumentContracts, boolean_edit
from research.observations.choose import Observations

OLD = 'class A:\n    arg_types = {"this": True, "optional": False}\n'
NEW = OLD.replace('"optional": False', '"optional": True')
ORIGIN = "sqlglot/a.py#A.arg_types"
REQUIRED = "sqlglot/b.py#Derived.required_args"


class ContractTests(unittest.TestCase):
    def test_only_one_boolean_token_is_supported(self):
        self.assertEqual(boolean_edit(OLD, NEW), ("A.arg_types", ["optional"]))
        for text in (
            NEW + "# comment\n",
            NEW.replace("class A:", "class B:"),
            NEW.replace('"this": True', '"this": False'),
            NEW.replace('"optional": True', '"extra": True'),
            NEW.replace("arg_types =", "arg_types  ="),
        ):
            self.assertIsNone(boolean_edit(OLD, text))

    def test_composed_schema_requires_an_exact_direct_boolean_edit(self):
        before = 'class A:\n    arg_types = {**Base.arg_types, "field": False}\n'
        after = before.replace('"field": False', '"field": True')
        self.assertEqual(boolean_edit(before, after), ("A.arg_types", ["field"]))
        self.assertIsNone(boolean_edit(before, after.replace("Base", "Other")))
        self.assertIsNone(boolean_edit(before, after + "# extra\n"))

    def test_computed_values_and_function_local_classes_are_not_supported(self):
        before = 'class A:\n    arg_types = {"field": bool(False)}\n'
        self.assertIsNone(boolean_edit(before, before.replace("False", "True")))
        before = 'def make():\n    class A:\n        arg_types = {"field": False}\n'
        self.assertIsNone(boolean_edit(before, before.replace("False", "True")))

    def contract(self):
        x = ArgumentContracts.__new__(ArgumentContracts)
        source_hash = hashlib.sha256(OLD.encode()).hexdigest()
        x.payload = dict(
            source={"sqlglot/a.py": source_hash},
            edges={ORIGIN + ":optional": [(ORIGIN, REQUIRED, "optional")]},
        )
        x.readers = dict(
            consumers={
                ORIGIN + ":keys": [0],
                ORIGIN + ":initialization": [1],
                ORIGIN + ":values": [2],
                REQUIRED + ":missing:optional": [3],
                REQUIRED + ":missing:this": [4],
                REQUIRED + ":required_missing": [5],
                REQUIRED + ":unknown": [6],
                REQUIRED + ":raw": [7],
            },
            test_shared={},
        )
        x.passed = set(range(11))
        x.index = SimpleNamespace(
            payload={
                "files": {"sqlglot/a.py": dict(source=OLD, sha256=source_hash)},
                "reads": {"sqlglot/a.py": [8]},
            },
            unobserved={9},
            all=set(range(12)),
            map_ids=set,
            file_consumers=lambda _: {10},
        )
        return x

    def patch(self):
        import difflib

        return "diff --git a/sqlglot/a.py b/sqlglot/a.py\n" + "".join(
            difflib.unified_diff(
                OLD.splitlines(True),
                NEW.splitlines(True),
                fromfile="a/sqlglot/a.py",
                tofile="b/sqlglot/a.py",
            )
        )

    def test_inherited_requiredness_and_raw_observers_survive(self):
        x = self.contract()
        # ID 11 has no complete baseline, ID 9 has no execution trace.
        self.assertEqual(
            x.narrow(self.patch(), set(range(12))), {2, 3, 5, 6, 7, 8, 9, 11}
        )

    def test_shared_test_setup_consumers_survive(self):
        x = self.contract()
        x.readers["test_shared"][REQUIRED] = ["tests/shared.py"]
        self.assertIn(10, x.narrow(self.patch(), set(range(12))))

    def test_application_import_validation_vetoes_runtime_only_narrowing(self):
        x = self.contract()
        x.readers["shared"] = [REQUIRED + ":missing:optional"]
        self.assertEqual(x.narrow(self.patch(), {2, 3, 4}), set(range(12)))

    def test_missing_propagation_or_source_mismatch_retains_everything(self):
        for mode in ("edges", "source"):
            x = self.contract()
            x.payload[mode] = {}
            self.assertEqual(x.narrow(self.patch(), set(range(12))), set(range(12)))

    def observation_guard(self):
        x = Observations.__new__(Observations)
        x.contracts = SimpleNamespace(narrow=lambda text, selected: set())
        x.passed = set(range(11))
        x.guarded = {9}
        x.map = {"metadata": {"sqlglot/a.py#A": [8]}, "shared_metadata": []}
        x.index = self.contract().index
        return x

    def test_code_and_resource_observers_survive_value_narrowing(self):
        x = self.observation_guard()
        self.assertEqual(x.narrow_arguments(self.patch(), set(range(12))), {8, 9, 11})

    def test_shared_code_observer_vetoes_value_narrowing(self):
        x = self.observation_guard()
        x.map["shared_metadata"] = ["sqlglot/a.py#A"]
        self.assertEqual(
            x.narrow_arguments(self.patch(), set(range(12))), set(range(12))
        )

    def test_import_hazard_widening_cannot_be_undone_by_metadata_guard(self):
        x = self.observation_guard()
        x.map["shared_metadata"] = ["sqlglot/a.py#A"]
        x.contracts = SimpleNamespace(narrow=lambda text, selected: set(range(12)))
        self.assertEqual(x.narrow_arguments(self.patch(), {2, 3, 4}), set(range(12)))


if __name__ == "__main__":
    unittest.main()
