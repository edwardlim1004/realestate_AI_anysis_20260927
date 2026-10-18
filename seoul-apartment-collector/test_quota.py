"""No-network safeguards test. Run with python seoul-apartment-collector/test_quota.py."""
import importlib.util
import json
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

spec=importlib.util.spec_from_file_location("collect",Path(__file__).with_name("collect.py"))
import sys
sys.path.insert(0,str(Path(__file__).parent))
collect=importlib.util.module_from_spec(spec)
spec.loader.exec_module(collect)

class FakeR2:
    files={}
    def migrate_legacy(self):pass
    def stats(self):return {"r2_compressed_bytes":0,"r2_scopes":0,"r2_objects_uploaded":0}
    def upload(self,*args):pass
    def save_manifest(self):pass

class FakeCollector:
    def __init__(self):
        self.calls=0
        self.limit=10
    def fetch(self,kind,gu,ym):
        self.calls+=1
        return []

def main():
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        with patch.object(collect,"DATA",root/"data"), \
             patch.object(collect,"STATE",root/"state.json"), \
             patch.object(collect,"STATUS",root/"status.json"), \
             patch.object(collect,"R2Storage",FakeR2), \
             patch.object(collect,"today",lambda:date(2026,10,18)):
            collect.save_json(collect.STATE,{"usage_day":"2026-10-18","daily_requests":4799})
            fake=FakeCollector()
            assert collect.run("test",10,3,districts=["11110"],collector=fake)==0
            status=json.loads(collect.STATUS.read_text(encoding="utf-8"))
            assert status["requests_today"]==4800,status
            assert status["daily_cap"]==4800,status
            assert fake.calls==1, fake.calls
            other=FakeCollector()
            assert collect.run("test",10,3,districts=["11110"],collector=other)==0
            assert other.calls==0,other.calls
            assert json.loads(collect.STATE.read_text(encoding="utf-8"))["daily_requests"]==4800
            print("PASS: shared daily cap, safe stop, status recording")
if __name__=="__main__": main()
