import sys,unittest,tempfile,importlib.util,difflib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
s=importlib.util.spec_from_file_location('cutpoint',ROOT/'research/incremental_executor/capsule.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class ContractTests(unittest.TestCase):
 def check(self,old,new,protected=()):
  with tempfile.TemporaryDirectory() as d:
   source=Path(d);path='sqlglot/optimizer/rule.py';p=source/path;p.parent.mkdir(parents=True);p.write_text(old)
   diff='diff --git a/'+path+' b/'+path+'\n'+''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+path,tofile='b/'+path))
   return m.eligible(source,diff,{'protected_files':list(protected)}),m.changed_functions(source,diff)
 def test_boolean_change_targets_function(self):
  decision,changed=self.check('def rule(a,b,c):\n return a and b and c\n','def rule(a,b,c):\n return a and b or c\n')
  self.assertTrue(decision[0]);self.assertEqual(changed,[('sqlglot/optimizer/rule.py','rule')])
 def test_reference_dependency_change_rejected(self):
  d,_=self.check('def f():\n return 1\n','def f():\n return 2\n',['sqlglot/optimizer/rule.py']);self.assertFalse(d[0])
 def test_signature_global_and_new_call_rejected(self):
  old='def f(x):\n return 1\n'
  for new in ('def f(x,y):\n return 1\n','flag=2\ndef f(x):\n return 1\n','def f(x):\n return other()\n'):
   self.assertFalse(self.check(old,new)[0][0])
 def test_comment_and_docstring_observers_not_silently_ignored(self):
  self.assertFalse(self.check('def f():\n return 1\n','def f():\n # comment\n return 1\n')[0][0])
  self.assertFalse(self.check('def f():\n "old"\n return 1\n','def f():\n "new"\n return 1\n')[0][0])
if __name__=='__main__':unittest.main()
