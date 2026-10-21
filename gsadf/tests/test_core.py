import unittest
import numpy as np
from gsadf.core import adf_t,recursive_statistics,date_episodes,simulate_critical_values
class CoreTests(unittest.TestCase):
 def test_constant(self): self.assertTrue(np.isnan(adf_t(np.ones(20),0,20)))
 def test_shape(self):
  x=recursive_statistics(np.cumsum(np.random.default_rng(7).normal(size=50)))
  self.assertEqual(len(x['bsadf']),50)
 def test_episodes(self):
  self.assertEqual(len(date_episodes(['a','b','c'],[False,True,True],2)),1)
 def test_mc(self):
  c=simulate_critical_values(48,3,7)
  self.assertTrue(np.isfinite(c['gsadf_95']))
if __name__=='__main__':unittest.main()
