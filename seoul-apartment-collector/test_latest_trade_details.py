import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import build_latest_trade_details as builder
from test_build_public_trade_details import FakeStore, RAW

class LatestTests(unittest.TestCase):
    def test_backwards_resume_and_revision(self):
        newer='rent/2026/11710/202609.csv.gz';older='rent/2026/11710/202608.csv.gz'
        store=FakeStore({newer:[{**RAW,'dealMonth':'9','deposit':'50000','monthlyRent':'0'}],
                         older:[{**RAW,'dealMonth':'8','deposit':'1000','monthlyRent':'80'}]})
        with tempfile.TemporaryDirectory() as d,patch.object(builder,'OUT',Path(d)/'latest'),patch.object(builder,'dashboard_periods',return_value=['202610','202611']):
            builder.build_region('송파구',store,1)
            p=builder.OUT/'11710.json';self.assertFalse(json.loads(p.read_text())['archive_scan_complete'])
            builder.build_region('송파구',store,1)
            data=json.loads(p.read_text());self.assertTrue(data['archive_scan_complete'])
            self.assertEqual({'monthly','jeonse'},{r['rentalType'] for r in data['rows']})
            self.assertEqual(2,len(data['rows']))
            builder.build_region('송파구',store,1);self.assertEqual(2,len(json.loads(p.read_text())['rows']))
            store.data[newer]=[{**store.data[newer][0],'cdealDay':'20261010'}];store.files[newer]['sha256']='b'*64
            builder.build_region('송파구',store,2)
            self.assertEqual(['monthly'],[r['rentalType'] for r in json.loads(p.read_text())['rows']])

    def test_latest_keeps_addresses_types_and_same_day_contracts(self):
        base={'code':'11710','apt':'동명단지','dong':'가락동','jibun':'1','date':'2026-01-01','rentalType':'sale'}
        rows=builder.merge_latest([base],[{**base,'date':'2026-02-01'},{**base,'date':'2026-02-01','area':'59'},
                                               {**base,'jibun':'2'},{**base,'rentalType':'monthly'}])
        self.assertEqual(4,len(rows));self.assertEqual(2,sum(r['date']=='2026-02-01' for r in rows))
if __name__=='__main__':unittest.main()
