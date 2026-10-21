import unittest
from gsadf.fetch_oecd import BASES, UNIT
class OecdQueryTests(unittest.TestCase):
    def test_every_measure_has_explicit_unit(self):
        self.assertEqual(UNIT["RHP"],"IX")
        self.assertEqual(UNIT["HPI_YDH_AVG"],"PT_AVG_L_TERM")
        self.assertEqual(UNIT["HPI_RPI_AVG"],"PT_AVG_L_TERM")
    def test_multiple_documented_oecd_paths(self):
        self.assertEqual(len(BASES),2)
        self.assertTrue(all("sdmx.oecd.org" in x for x in BASES))
if __name__=="__main__":unittest.main()
