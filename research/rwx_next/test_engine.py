import sys,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent/'rwx'))
from engine.core import differential_value,semantic_edits
from engine.runner import PatchedTree

class EngineTests(unittest.TestCase):
    def test_value_at_boundary_and_direction(self):
        self.assertEqual(differential_value('x > 10','x > 11',{'x':10})['status'],'same')
        self.assertEqual(differential_value('x > 10','x > 11',{'x':11})['status'],'changed')
        self.assertEqual(differential_value('x > 10','x > 9',{'x':10})['status'],'changed')
    def test_unknown_calls_and_overloaded_objects(self):
        self.assertEqual(differential_value('f(x)','f(x)',{'x':1})['status'],'unknown')
        self.assertEqual(differential_value('x > 1','x > 2',{'x':object()})['status'],'unknown')
    def test_short_circuit_does_not_evaluate_unknown_branch(self):
        self.assertEqual(differential_value('False and f()','False and g()',{})['status'],'same')
    def test_raw_observer_change_survives_equal_ast(self):
        e=semantic_edits('x=1\n','x=1 # changed\n')
        self.assertTrue(e['raw_changed']);self.assertFalse(e['ast_changed'])
    def test_patch_does_not_mutate_baseline(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'sqlglot').mkdir();(root/'tests').mkdir();p=root/'sqlglot/a.py';p.write_text('x=1\n')
            patch='diff --git a/sqlglot/a.py b/sqlglot/a.py\n--- a/sqlglot/a.py\n+++ b/sqlglot/a.py\n@@ -1 +1 @@\n-x=1\n+x=2\n'
            with PatchedTree(root,patch) as t:self.assertEqual((t.path/'sqlglot/a.py').read_text(),'x=2\n')
            self.assertEqual(p.read_text(),'x=1\n')
class IPCDependencyTests(unittest.TestCase):
    def test_process_transport_consumer_includes_serialization_import(self):
        from engine.ipc import consumers
        p={'files':{'sqlglot/object.py':{'source':'class Obj:\n def __getstate__(self):\n  from sqlglot.codec import encode\n  return encode(self)\n'},'sqlglot/codec.py':{'source':'def encode(x): return x\n'},'tests/test_worker.py':{'source':'from multiprocessing import Process\np=Process()\n'}}}
        result=consumers(p,[{'number':9,'file':'tests/test_worker.py'},{'number':10,'file':'tests/test_other.py'}])
        self.assertEqual(result['sqlglot/codec.py'],[9])
        self.assertEqual(result['sqlglot/object.py'],[9])
if __name__=='__main__':unittest.main()
