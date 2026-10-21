import csv
import json
import tempfile
import unittest
from pathlib import Path
from gsadf.storage import build_bundle
from gsadf.change_check import fingerprint,decide
class StorageTests(unittest.TestCase):
 def fixture(self,root,approval="PENDING_INDEPENDENT_VALIDATION"):
  data=root/"data";out=root/"output";(data/"raw").mkdir(parents=True);out.mkdir()
  for key in ("real_hpi","pir","ptr"):
   (data/f"korea_{key}_quarterly.csv").write_text("period,value,source_id\\n2025-Q1,100,OECD\\n",encoding="utf-8")
   (data/"raw"/(key+"_20261022T000000Z.csv")).write_text("source archive",encoding="utf-8")
   (out/(key+".json")).write_text(json.dumps({"approval":approval,"eligibleForComposite":False,"method":{"MC_repetitions":2000}}),encoding="utf-8")
  return data,out
 def test_bundle_hash_stable(self):
  with tempfile.TemporaryDirectory() as d:
   data,out=self.fixture(Path(d))
   self.assertEqual(build_bundle(data,out),build_bundle(data,out))
 def test_fail_closed_approval(self):
  with tempfile.TemporaryDirectory() as d:
   data,out=self.fixture(Path(d),"APPROVED")
   with self.assertRaises(RuntimeError):build_bundle(data,out)
 def test_change_fingerprint(self):
  with tempfile.TemporaryDirectory() as d:
   data,out=self.fixture(Path(d))
   previous=fingerprint(data)
   (data/".previous_series_sha256").write_text(previous,encoding="ascii")
   self.assertFalse(decide(data))
   (data/"korea_pir_quarterly.csv").write_text("period,value,source_id\\n2025-Q1,101,OECD\\n",encoding="utf-8")
   self.assertTrue(decide(data))
if __name__=="__main__":unittest.main()
