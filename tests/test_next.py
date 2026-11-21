import sys,unittest,tempfile,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from engine.ipc import consumers
from engine.selection import adaptive_select

class TransportTests(unittest.TestCase):
 def test_alias_and_helper_transitive_closure(self):
  sources={
  'sqlglot/state.py':'from sqlglot.codec import pack as encode\nclass State:\n def __reduce__(self): return local(self)\ndef local(x): return encode(x)\n',
  'sqlglot/codec.py':'from sqlglot.wire import write\ndef pack(x): return write(x)\n',
  'sqlglot/wire.py':'def write(x): return x\n',
  'tests/test_parallel.py':'from concurrent.futures import ProcessPoolExecutor as Jobs\ndef f(): return Jobs()\n'}
  edges=consumers({'files':{p:{'source':s} for p,s in sources.items()}},[{'file':'tests/test_parallel.py','number':5}])
  for file in ('sqlglot/state.py','sqlglot/codec.py','sqlglot/wire.py'):self.assertEqual(edges[file],[5])
 def test_colliding_import_aliases_are_unioned(self):
  sources={'sqlglot/state.py':'class State:\n def __reduce__(self):\n  from sqlglot.a import pack\n  return pack(self)\ndef unrelated():\n from sqlglot.b import pack\n return pack(None)\n','sqlglot/a.py':'def pack(x): return x\n','sqlglot/b.py':'def pack(x): return x\n','tests/p.py':'from multiprocessing import Pool as P\nx=P\n'}
  edges=consumers({'files':{p:{'source':s} for p,s in sources.items()}},[{'file':'tests/p.py','number':7}])
  self.assertEqual(edges['sqlglot/a.py'],[7]);self.assertEqual(edges['sqlglot/b.py'],[7])

class GranularityTests(unittest.TestCase):
 def test_only_initialization_fallback_switches_to_broad(self):
  class Index:
   def select(self,text,mode):return ({1},'module_or_class_level_change') if mode=='impact' else ({1,2},'source_module_evidence')
  self.assertEqual(adaptive_select(Index(),'unused')[0],{1,2})
 def test_unknown_evidence_stays_full(self):
  class Index:
   def select(self,text,mode):return {1,2,3},'changed_scope_without_test_evidence'
  self.assertEqual(adaptive_select(Index(),'unused')[0],{1,2,3})
 def test_empty_reader_certificate_is_preserved(self):
  class Index:
   def select(self,text,mode):return set(),'supported_nonimpact_empty'
  self.assertEqual(adaptive_select(Index(),'unused')[0],set())

if __name__=='__main__':unittest.main()
