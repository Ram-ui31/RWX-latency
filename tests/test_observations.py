"""Regression checks for observations that could otherwise omit a failing test."""
import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research.observations import probe
from research.observations.choose import operand_site, observed_artifacts, plain_comment
from blast.patches import parse_patch


class ObservationTests(unittest.TestCase):
    def test_equal_distinct_strings_are_unsafe_for_identity_replacement(self):
        a = ''.join(['independently', ' allocated'])
        b = ''.join(['independently ', 'allocated'])
        self.assertIsNot(a, b)
        self.assertEqual(probe.relation(a, b), probe.OBSERVED_DISTINCT_EQUAL)

    def test_custom_equality_is_unknown_and_never_invoked(self):
        class Unknown:
            def __eq__(self, other):
                raise AssertionError('profiling invoked user equality')
        self.assertEqual(probe.relation(Unknown(), None), probe.UNKNOWN)

    def test_default_identity_equality_and_none(self):
        class Item:
            pass
        self.assertEqual(probe.relation(Item(), None), probe.OBSERVED_UNEQUAL)
        self.assertEqual(probe.relation(None, None), probe.OBSERVED_SAME)

    def test_only_exactly_one_supported_operator_change_matches(self):
        before = 'def f(a, b):\n    return a is b\n'
        after = before.replace('is', '==')
        self.assertEqual(operand_site(before, after, 'x.py'), ('x.py:2:11', 5))
        self.assertIsNone(operand_site(before, after.replace('return', 'yield'), 'x.py'))
        self.assertIsNone(operand_site(before, before.replace('is', '!='), 'x.py'))

    def test_order_boundary_is_retained(self):
        probe.active = 'boundary'
        probe.values.clear()
        self.assertFalse(probe.observe_order('x', (2, 3), (2, 3), 'Lt'))
        self.assertEqual(probe.values['boundary']['x'], probe.OBSERVED_SAME)
        before = 'def f(a):\n    return a < (2, 3)\n'
        self.assertEqual(operand_site(before, before.replace('<', '<='), 'x.py')[1], 4)
        probe.active = None

    def test_multiple_operator_edits_rejected(self):
        a = 'def f(a,b):\n    return (a is b, b is a)\n'
        self.assertIsNone(operand_site(a, a.replace('is', '=='), 'x.py'))

    def test_only_changed_code_metadata_observers_guarded(self):
        before = 'def first():\n    return 1\ndef second():\n    return 2\n'
        after = before.replace('return 2', '# Plain comment\n    return 2')
        artifacts = observed_artifacts(before, after, 'x.py')
        self.assertIn('x.py', artifacts)
        self.assertIn('x.py#second', artifacts)
        self.assertNotIn('x.py#first', artifacts)

    def test_comment_rule_rejects_docstring_and_directive_changes(self):
        import difflib
        def is_comment(a, b):
            text = 'diff --git a/x.py b/x.py\n'+''.join(difflib.unified_diff(
                a.splitlines(True), b.splitlines(True), fromfile='a/x.py', tofile='b/x.py'))
            return plain_comment(parse_patch(text)[0], a, b)
        a = 'def f():\n    return 1\n'
        self.assertTrue(is_comment(a, '# A plain comment\n'+a))
        self.assertFalse(is_comment(a, '# coding: latin-1\n'+a))
        self.assertFalse(is_comment(a, a.replace('return 1', '"new docstring"\n    return 1')))

    def test_default_entrypoint_uses_observation_output_without_checkpoint_stage(self):
        import contextlib
        import importlib.util
        import io
        import json
        import os
        import tempfile
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location('observation_candidate', ROOT/'run_candidate.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage = root/'research/tail_verifier'
            stage.mkdir(parents=True)
            (stage/'evaluate.py').write_text(
                "import sys,json\nfrom pathlib import Path\n"
                "assert '--observations' in sys.argv\n"
                "Path(sys.argv[sys.argv.index('--predictions')+1]).write_text("
                "json.dumps({'commit':'example','workers':[]})+'\\n')\n")
            module.ROOT = root
            out = io.StringIO()
            with patch.dict(os.environ, RWX_OBSERVATIONS='/baseline/map.json.gz'):
                with tempfile.TemporaryFile(mode='w+t') as err:
                    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                        module.main()
            self.assertEqual(json.loads(out.getvalue()), {'commit':'example','workers':[]})


if __name__ == '__main__':
    unittest.main()
