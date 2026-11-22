import unittest
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.astdiff import classify  # noqa: E402
from engine.reduce import reduce_patch  # noqa: E402

OLD = '''"""Module doc."""
import os

X = 1


class A:
    """Class doc."""
    FLAG = False
    TABLE = {"a": lambda self: self.one(), "b": 2}

    def f(self, y):
        """Function doc."""
        if y > 1:
            return y
        return 0
'''


class TestClassify(unittest.TestCase):
    def kind(self, new):
        return classify(OLD, new)

    def test_docstrings_and_comments_are_noop(self):
        new = OLD.replace('"""Function doc."""', '"""Changed doc."""').replace('    FLAG = False', '    # note\n    FLAG = False')
        self.assertEqual(self.kind(new)[0], 'noop')

    def test_body_edit_reports_old_lines(self):
        kind, spans, lambdas = self.kind(OLD.replace('if y > 1:', 'if y >= 1:'))
        self.assertEqual(kind, 'body')
        self.assertIn((14, 14), spans)
        self.assertEqual(lambdas, [])

    def test_inserted_statement_reports_neighbours(self):
        kind, spans, _ = self.kind(OLD.replace('            return y\n', '            y += 1\n            return y\n'))
        self.assertEqual(kind, 'body')
        self.assertIn((15, 15), spans)

    def test_class_setting_is_value(self):
        kind, targets, _ = self.kind(OLD.replace('FLAG = False', 'FLAG = True'))
        self.assertEqual(kind, 'value')
        self.assertEqual(targets[0][1], ['FLAG'])

    def test_lambda_body_in_class_dict_is_call_time(self):
        kind, spans, lambdas = self.kind(OLD.replace('self.one()', 'self.two()'))
        self.assertEqual(kind, 'body')
        self.assertEqual(lambdas, [10])

    def test_dict_key_is_value_and_import_is_structural(self):
        self.assertEqual(self.kind(OLD.replace('"b": 2', '"bx": 2'))[0], 'value')
        self.assertEqual(self.kind(OLD.replace('import os', 'import sys'))[0], 'import')
        self.assertEqual(self.kind(OLD.replace('    def f(self, y):', '    def f(self, y=1):'))[0], 'import')


class TestSignatureDefaults(unittest.TestCase):
    SRC = 'from __future__ import annotations\n\n\ndef f(a, copy: bool = True, rules=RULES):\n    return a\n'

    def test_constant_default_flip_is_call_time(self):
        kind, spans, calls = classify(self.SRC, self.SRC.replace('copy: bool = True', 'copy: bool = False'))
        self.assertEqual((kind, calls), ('body', [4]))

    def test_non_constant_default_is_structural(self):
        self.assertEqual(classify(self.SRC, self.SRC.replace('= True', '= OTHER'))[0], 'import')

    def test_new_parameter_is_structural(self):
        self.assertEqual(classify(self.SRC, self.SRC.replace('(a, ', '(a, b=1, '))[0], 'import')


class FakeIndex:
    payload = {'reads': {}}

    def map_ids(self, ids):
        return set()


class TestReduce(unittest.TestCase):
    def test_docstring_hunk_dropped_code_hunk_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'sqlglot').mkdir()
            body = ['"""Doc line."""\n'] + [f'A{i} = {i}\n' for i in range(30)]
            (root / 'sqlglot/m.py').write_text(''.join(body))
            patch = ('diff --git a/sqlglot/m.py b/sqlglot/m.py\n--- a/sqlglot/m.py\n+++ b/sqlglot/m.py\n'
                     '@@ -1,2 +1,2 @@\n-"""Doc line."""\n+"""Doc lines."""\n A0 = 0\n'
                     '@@ -29,3 +29,3 @@\n A27 = 27\n-A28 = 28\n+A28 = 29\n A29 = 29\n')
            reduced, extra, dropped = reduce_patch(root, patch, FakeIndex())
            self.assertIn('-A28 = 28', reduced)
            self.assertNotIn('Doc lines', reduced)
            self.assertEqual(dropped, ['sqlglot/m.py:1/2'])
            only_doc = patch.split('@@ -29')[0]
            reduced, _, dropped = reduce_patch(root, only_doc, FakeIndex())
            self.assertEqual(reduced, '')
            self.assertEqual(dropped, ['sqlglot/m.py:all'])


if __name__ == '__main__':
    unittest.main()
