"""Ground truth must account for import errors and incomplete execution."""

import unittest
from tools.argument_holdout import reference_outcomes


class ReferenceLabelsTests(unittest.TestCase):
    ids = {
        "tests/bad.py::C::one": 0,
        "tests/bad.py::C::two": 1,
        "tests/good.py::C::one": 2,
    }

    def test_failed_import_fails_every_numbered_test_in_the_file(self):
        data = {
            "collection": ["tests/bad.py"],
            "reports": [
                {"nodeid": "tests/good.py::C::one", "when": "call", "outcome": "passed"}
            ],
        }
        result = reference_outcomes(data, self.ids, 1)
        self.assertEqual(
            result, dict(failing=[0, 1], whole_tests=3, collection_failures=2)
        )

    def test_setup_failure_counts_even_without_a_call(self):
        data = {
            "collection": [],
            "reports": [
                {
                    "nodeid": node,
                    "when": "setup" if number == 0 else "call",
                    "outcome": "failed" if number == 0 else "passed",
                }
                for node, number in self.ids.items()
            ],
        }
        self.assertEqual(reference_outcomes(data, self.ids, 1)["failing"], [0])

    def test_unexecuted_tests_are_not_silently_labeled_passed(self):
        data = {
            "collection": [],
            "reports": [
                {"nodeid": "tests/good.py::C::one", "when": "call", "outcome": "passed"}
            ],
        }
        with self.assertRaises(ValueError):
            reference_outcomes(data, self.ids, 0)


if __name__ == "__main__":
    unittest.main()
