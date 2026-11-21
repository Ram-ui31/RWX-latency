import difflib,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from engine.fixture_adapter import plan

def diff(old,new,path):
 return 'diff --git a/'+path+' b/'+path+'\n'+''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+path,tofile='b/'+path))

class AdapterEligibility(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.source=ROOT.parent/'fourthon/rwx/source/sqlglot'
  if not cls.source.exists():raise unittest.SkipTest('Pinned research checkout needed for contract eligibility tests')
  cls.catalog=json.loads((ROOT.parent/'fourthon/rwx/sample/sample/tests.json').read_text())['tests']
  cls.path='tests/fixtures/optimizer/pushdown_predicates.sql';cls.old=(cls.source/cls.path).read_text()
 def test_new_expectation_is_preserved(self):
  from blast.fixture_contracts import normalize
  expected=normalize(self.old,'pairs')[0][2]
  new=self.old.replace(expected,expected+' /* independently changed expectation */',1)
  p=plan(self.source,diff(self.old,new,self.path),self.catalog)
  self.assertTrue(p['eligible']);self.assertNotEqual(p['before'],p['after']);self.assertFalse(p['omission_authorized'])
 def test_native_metadata_disables_replay(self):
  new='# execute: true\n'+self.old
  p=plan(self.source,diff(self.old,new,self.path),self.catalog)
  self.assertFalse(p['eligible']);self.assertEqual(p['reason'],'native_execution_metadata')
 def test_record_deletion_disables_replay(self):
  p=plan(self.source,diff(self.old,'SELECT 1; SELECT 1;\n',self.path),self.catalog)
  self.assertEqual(p['reason'],'record_order_or_count_changed')
 def test_malformed_patch_stays_unknown(self):
  self.assertEqual(plan(self.source,'bad patch',self.catalog)['reason'],'invalid_patch')
 def test_source_edit_disables_replay(self):
  p=plan(self.source,diff('x=1\n','x=2\n','sqlglot/example.py'),self.catalog)
  self.assertEqual(p['reason'],'unsupported_fixture')
if __name__=='__main__':unittest.main()
