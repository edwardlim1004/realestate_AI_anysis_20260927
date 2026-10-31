"""No-network validation of Daejeon snapshots. Run via Actions before publishing."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

BASE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("daejeon_build",BASE/"build_daejeon.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class FakeArchive:
    def __init__(self, months, missing=None):
        self.files={}
        self.rows={}
        for code in mod.DAEJEON:
            for ym in months:
                for kind in ("sale","rent"):
                    key=f"{kind}/{ym[:4]}/{code}/{ym}.csv.gz"
                    if key==missing: continue
                    rows=[]
                    for i in range(6):
                        basic={"aptNm":"검증아파트","umdNm":"대동","jibun":"12-3",
                               "excluUseAr":"84.95","dealYear":ym[:4],
                               "dealMonth":str(int(ym[-2:])),"dealDay":str(8+i),
                               "floor":"9","buildYear":"2004","cdealDay":""}
                        if kind=="sale":
                            basic["dealAmount"]=str(50000 + int(ym[:4])*2 + int(ym[-2:])*10)
                        else:
                            basic["deposit"]=str(30000 + int(ym[-2:])*5)
                            basic["monthlyRent"]="0"
                        rows.append(basic)
                    self.rows[key]=rows
                    self.files[key]={"sha256":"a"*64,"storage":"r2","rows":len(rows)}
    def read_scope(self,key):return self.rows[key]

class TestDaejeon(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old_output=mod.OUTPUT
        self.old_valuation=mod.VALUATION
        mod.OUTPUT=Path(self.tmp.name)/"district"
        mod.VALUATION=Path(self.tmp.name)/"value"
        self.months=[mod.five.shift_month("202609",i) for i in range(-59,1)]
    def tearDown(self):
        mod.OUTPUT=self.old_output
        mod.VALUATION=self.old_valuation
        self.tmp.cleanup()
    def test_5_districts_and_never_fake_risk(self):
        archive=FakeArchive(self.months)
        result=mod.main(["--cutoff","202609"],storage=archive)
        self.assertEqual(len(result["regions"]),5)
        self.assertEqual(result["status"],"RESEARCH_ONLY")
        for r in result["regions"]:
            self.assertEqual(r["scope_coverage"],"120/120 verified")
            self.assertEqual(r["train_months"],48)
            self.assertEqual(r["holdout_months"],12)
            self.assertIsNotNone(r["gapPct"])
            self.assertIsNotNone(r["partialScore4of5"])
            self.assertFalse(r["riskVerified"])
            self.assertNotIn("composite",r)
            val=json.loads((mod.VALUATION/"data"/(r["code"]+".json")).read_text())
            self.assertEqual(val["coverage"]["missing_scopes"],0)
            self.assertEqual(val["coverage"]["scopes_verified"],120)
            self.assertGreater(val["complex_count"],0)
        disk=json.loads((mod.OUTPUT/"daejeon-regions.json").read_text())
        self.assertEqual(disk["cutoff_month"],"202609")
    def test_missing_source_fails_closed(self):
        missing=f"sale/2026/30110/202609.csv.gz"
        archive=FakeArchive(self.months,missing=missing)
        with self.assertRaisesRegex(ValueError,"missing or unverified"):
            mod.main(["--cutoff","202609"],storage=archive)
        self.assertFalse((mod.OUTPUT/"daejeon-regions.json").exists())
        self.assertFalse((mod.VALUATION/"data"/"30110.json").exists())
    def test_cancelled_monthly_and_no_monthly_rent_equivalence(self):
        sold={"aptNm":"Test","umdNm":"대동","jibun":"3","excluUseAr":"84.5",
              "dealYear":"2026","dealMonth":"9","dealDay":"14",
              "dealAmount":"70000","cdealDay":"2026-10-12"}
        self.assertIsNone(mod.normalize("sale","30110","202609",sold))
        deposit={"aptNm":"Test","umdNm":"대동","jibun":"3","excluUseAr":"84.5",
                 "dealYear":"2026","dealMonth":"9","dealDay":"14",
                 "deposit":"50000","monthlyRent":"100"}
        self.assertIsNone(mod.normalize("rent","30110","202609",deposit))

if __name__=="__main__":unittest.main()
