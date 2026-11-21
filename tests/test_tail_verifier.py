import importlib.util,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
s=importlib.util.spec_from_file_location('tail',ROOT/'research/tail_verifier/evaluate.py');tail=importlib.util.module_from_spec(s);s.loader.exec_module(tail)
class TailPriorityTests(unittest.TestCase):
 def test_priority_is_marginal_schedule_cost(self):
  ds={0:21000,1:100,2:100}
  gain,n=tail.best_action(set(ds),ds,set())
  self.assertEqual(n,0);self.assertGreater(gain,20)
 def test_failed_or_unknown_action_is_not_retried(self):
  gain,n=tail.best_action({0},{0:21000},{0})
  self.assertEqual(gain,0);self.assertIsNone(n)
 def test_empty_selection_has_no_action(self):
  self.assertEqual(tail.best_action(set(),{},set()),(0,None))
class CostGateTests(unittest.TestCase):
 def test_expensive_and_unmeasured_actions_rejected(self):
  from engine.verification_budget import gate
  self.assertFalse(gate(21,60,{'status':'observed_pass','total_cpu_seconds':28})['allowed'])
  self.assertFalse(gate(21,60,None)['allowed'])
 def test_cheap_action_requires_remaining_budget(self):
  from engine.verification_budget import gate
  p={'status':'observed_pass','total_cpu_seconds':1}
  self.assertTrue(gate(6,10,p)['allowed']);self.assertFalse(gate(6,1,p)['allowed'])
 def test_invalid_cost_is_not_a_discount(self):
  from engine.verification_budget import gate
  for cost in [-1,float('nan'),float('inf'),True]:
   self.assertFalse(gate(20,60,{'status':'observed_pass','total_cpu_seconds':cost})['allowed'])
if __name__=='__main__':unittest.main()
