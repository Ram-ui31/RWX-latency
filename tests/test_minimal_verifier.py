"""Check that incomplete tests and failed fixtures never authorize omission."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.group_verifier.minimal import execute


class MinimalVerifierTests(unittest.TestCase):
    def run_cases(self, body, names):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)
            module = "rwx_synthetic_" + str(id(source))
            (source / (module + ".py")).write_text("import unittest\n" + body)
            output = source / "result.json"
            nodes = [module + ".py::Cases::" + name for name in names]
            try:
                execute(source, nodes, output)
                return json.loads(output.read_text()), nodes
            finally:
                sys.modules.pop(module, None)
                sys.path.remove(str(source.resolve()))

    def test_successful_subtests_do_not_stop_the_suite(self):
        result, nodes = self.run_cases(
            "class Cases(unittest.TestCase):\n"
            " def test_first(self):\n"
            "  for i in range(3):\n"
            "   with self.subTest(i=i):self.assertEqual(i,i)\n"
            " def test_second(self):self.assertTrue(True)\n",
            ["test_first", "test_second"],
        )
        self.assertEqual(set(result["passed"]), set(nodes))

    def test_failing_subtest_and_unexecuted_tests_are_retained(self):
        result, nodes = self.run_cases(
            "class Cases(unittest.TestCase):\n"
            " def test_first(self):self.assertTrue(True)\n"
            " def test_second(self):\n"
            "  with self.subTest():self.assertTrue(False)\n"
            " def test_third(self):self.assertTrue(True)\n",
            ["test_first", "test_second", "test_third"],
        )
        self.assertEqual(result["passed"], nodes[:1])

    def test_failed_class_teardown_invalidates_passes(self):
        result, _ = self.run_cases(
            "class Cases(unittest.TestCase):\n"
            " @classmethod\n"
            ' def tearDownClass(cls):raise RuntimeError("cleanup failed")\n'
            " def test_first(self):self.assertTrue(True)\n",
            ["test_first"],
        )
        self.assertTrue(result["lifecycle_error"])
        self.assertEqual(result["passed"], [])

    def test_skipped_test_is_unresolved(self):
        result, _ = self.run_cases(
            "class Cases(unittest.TestCase):\n"
            ' @unittest.skip("unavailable")\n'
            " def test_first(self):pass\n",
            ["test_first"],
        )
        self.assertEqual(result["passed"], [])
