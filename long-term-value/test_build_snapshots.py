"""Offline regression tests. Run: python -m unittest discover -s long-term-value -p 'test_*.py'"""
import collections
import csv
import gzip
import hashlib
import io
import unittest
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("valuation_build", Path(__file__).with_name("build_snapshots.py"))
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def gzip_csv(rows):
    stream = io.StringIO()
    columns = ["단지명","법정동","지번","전용면적(㎡)","계약일","해제사유발생일","거래금액(만원)","보증금(만원)","월세금(만원)"]
    out = csv.DictWriter(stream, fieldnames=columns)
    out.writeheader()
    for item in rows:
        out.writerow(item)
    return gzip.compress(stream.getvalue().encode("utf-8-sig"))


def row(**kw):
    return {"단지명":"시험아파트","법정동":"가동","지번":"101",
            "전용면적(㎡)":"84.97","계약일":"2026-09-15",
            "해제사유발생일":"","거래금액(만원)":"120,000",
            "보증금(만원)":"70,000","월세금(만원)":"0",**kw}


class ValuationTest(unittest.TestCase):
    def test_calendar(self):
        self.assertEqual(build.shift_month("202601",-1),"202512")
        self.assertEqual(len([build.shift_month("202609",i) for i in range(-59,1)]),60)

    def test_cancelled_trade_and_month_mismatch(self):
        bags=collections.defaultdict(lambda: {"sale":collections.defaultdict(list),"rent":collections.defaultdict(list)})
        payload=gzip_csv([row(),row(**{"해제사유발생일":"2026-10-01"}),row(**{"계약일":"2026-08-15"})])
        self.assertEqual(build.parse_scope(payload,"sale","202609",bags),1)
        self.assertEqual(bags[("가동","시험아파트","101",85)]["sale"]["202609"],[120000])

    def test_pure_jeonse_only(self):
        bags=collections.defaultdict(lambda: {"sale":collections.defaultdict(list),"rent":collections.defaultdict(list)})
        payload=gzip_csv([row(),row(**{"월세금(만원)":"100"})])
        self.assertEqual(build.parse_scope(payload,"rent","202609",bags),1)

    def test_median_and_quality_fields(self):
        sales=collections.defaultdict(list)
        rents=collections.defaultdict(list)
        sales["202110"]=[100000,110000,120000]
        sales["202609"]=[140000,150000,160000,170000,180000]
        rents["202609"]=[80000,81000,82000]
        months=[build.shift_month("202609",i) for i in range(-59,1)]
        c=build.make_complex(("가동","시험아파트","101",85),
          {"sale":sales,"rent":rents},months,"202609")
        self.assertEqual(c["last12_median"],160000)
        self.assertEqual(c["last12_count"],5)
        self.assertEqual(c["first12_median"],110000)
        self.assertAlmostEqual(c["jeonse_rate_pct"],50.6)
        self.assertTrue(c["observed_cagr_pct"]>0)

    def test_manifest_scope_checksum(self):
        months=["202608","202609"]
        m={"files":{"sale/2026/11710/202609.csv.gz":{"sha256":"abcdef","storage":"r2"}}}
        present,missing,digest=build.source_digests(m,"11710",months)
        self.assertEqual(len(present),1)
        self.assertEqual(len(missing),3)
        self.assertEqual(len(digest),64)


if __name__=="__main__":
    unittest.main()
