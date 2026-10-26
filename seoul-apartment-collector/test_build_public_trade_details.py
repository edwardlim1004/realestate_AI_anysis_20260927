# coding: utf-8
"""Offline tests: zero API/R2 network needed."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
SPEC = importlib.util.spec_from_file_location("trade_builder", HERE / "build_public_trade_details.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)

class FakeStore:
    def __init__(self, data):
        self.data = data
        self.files = {
            key: {"sha256": "a"*64, "rows": len(rows), "storage":"r2"}
            for key, rows in data.items()
        }
    def read_scope(self, relative):
        return self.data[relative]

RAW = {
    "aptNm":"분당테스트아파트", "umdNm":"정자동", "jibun":"123",
    "excluUseAr":"84.97", "dealAmount":"120,000",
    "dealYear":"2026","dealMonth":"10","dealDay":"10","floor":"12",
    "buildYear":"2009", "cdealDay":"", "dealingGbn":"중개거래"
}

class TradeDetailTest(unittest.TestCase):
    def setUp(self):
        self.old_output = builder.OUTPUT
        self.temp = tempfile.TemporaryDirectory()
        builder.OUTPUT = Path(self.temp.name)
    def tearDown(self):
        builder.OUTPUT = self.old_output
        self.temp.cleanup()
    def test_gyeonggi_region_and_public_content(self):
        codes = builder.REGION_LAWD["성남시 (분당/판교)"]
        self.assertEqual(codes, ["41135"])
        source = builder.entry_key("41135","202610")
        store = FakeStore({source: [RAW, {**RAW, "cdealDay":"2026-10-13"}]})
        out = builder.build_region("성남시 (분당/판교)", codes, ["202610"],store,store.files)
        self.assertEqual(out["status"],"updated")
        payload = json.loads((builder.OUTPUT/"41135.json").read_text())
        self.assertEqual(payload["by_month"]["202610"],1)
        self.assertEqual(payload["excluded_rows"],1)
        self.assertEqual(payload["rows"][0]["city"],"경기도 성남시 분당구")
        self.assertEqual(payload["rows"][0]["price"],"120000")
        self.assertNotIn("원본항목JSON",json.dumps(payload))
        out2=builder.build_region("성남시 (분당/판교)", codes, ["202610"],store,store.files)
        self.assertEqual(out2["status"],"unchanged")
    def test_missing_scope_never_mints_transactions(self):
        output=builder.build_region("송파구",["11710"],["202609","202610"],FakeStore({}),{})
        self.assertEqual(output["status"],"missing_source")
        self.assertFalse((builder.OUTPUT/"11710.json").exists())
    def test_multi_code_region_partition(self):
        codes=builder.REGION_LAWD["고양시 (일산/덕양)"]
        self.assertEqual(len(codes),3)
        data={builder.entry_key(code,"202610"):[{**RAW,"aptNm":code}] for code in codes}
        store=FakeStore(data)
        out=builder.build_region("고양시 (일산/덕양)",codes,["202610"],store,store.files)
        self.assertEqual(out["count"],3)
        payload=json.loads((builder.OUTPUT/f"{codes[0]}.json").read_text())
        self.assertEqual(len({x["code"] for x in payload["rows"]}),3)

if __name__=="__main__":
    unittest.main()
