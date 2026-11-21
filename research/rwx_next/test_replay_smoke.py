"""Positive/error controls for observation collection, not omission safety."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


class ReplayObservationControls(unittest.TestCase):
    def test_failures_subtests_errors_and_skips_are_not_reported_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'replay_control.py').write_text('''import unittest
class Controls(unittest.TestCase):
    def test_pass(self): self.assertEqual(1, 1)
    def test_fail(self): self.assertEqual(1, 2)
    def test_subtests(self):
        for x in range(3):
            with self.subTest(x=x): self.assertLess(x, 2)
    def test_error(self): raise RuntimeError('control')
    @unittest.skip('control')
    def test_skip(self): pass
''')
            names = ['test_pass', 'test_fail', 'test_subtests', 'test_error', 'test_skip']
            tests = [dict(number=i, file='replay_control.py',
                          id=f'replay_control.py::Controls::{name}') for i, name in enumerate(names)]
            result = root / 'result.json'
            job = root / 'job.json'
            job.write_text(json.dumps(dict(tree=str(root), tests=tests, result=str(result))))
            proc = subprocess.run([sys.executable, '-B', str(HERE / 'replay_smoke.py'), '--child', str(job)],
                                  capture_output=True, text=True, timeout=15)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            observed = json.loads(result.read_text())
            self.assertEqual(observed['tests_run'], 5)
            self.assertEqual(observed['observed_failures'], [1, 2])
            self.assertEqual(observed['unknown'], [3, 4])

    def test_import_failure_is_unknown(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'broken_control.py').write_text("raise ImportError('control')\n")
            result = root / 'result.json'
            job = root / 'job.json'
            job.write_text(json.dumps(dict(tree=str(root), result=str(result), tests=[
                dict(number=9, file='broken_control.py', id='broken_control.py::Controls::test_x')
            ])))
            proc = subprocess.run([sys.executable, '-B', str(HERE / 'replay_smoke.py'), '--child', str(job)],
                                  capture_output=True, text=True, timeout=15)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(result.read_text())['unknown'], [9])


if __name__ == '__main__':
    unittest.main()
