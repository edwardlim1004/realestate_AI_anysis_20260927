"""Research-only ECOS stock and bond collection: fast tests without external API."""
from __future__ import annotations
import datetime as dt
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parents[2] / 'risk-monitor/liquidity/update_asset_transmission.py'
SPEC=importlib.util.spec_from_file_location('shadow_assets',SOURCE)
module=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class MarketCollectionTests(unittest.TestCase):
    def test_kospi_uses_quarter_final_close(self):
        data=[('20250103',2510.0),('20250204',2650.0),('20250331',2755.1),('20250401',2600.0)]
        result=module.aggregate_quarterly('KOSPI',data)
        self.assertEqual([d['Quarter'] for d in result],['2025-Q1','2025-Q2'])
        self.assertAlmostEqual(float(result[0]['Value']),2755.1)
        self.assertEqual(result[0]['ObservationCount'],'3')
    def test_bond_is_arithmetic_trading_day_mean(self):
        result=module.aggregate_quarterly('KTB3Y',[('20250102',2.3),('20250103',2.5),('20250105',2.9)])
        self.assertAlmostEqual(float(result[0]['Value']),(2.3+2.5+2.9)/3)
    def test_reject_non_official_stat_code(self):
        def fake(_url):
            return {'StatisticSearch':{'list_total_count':1,'row':[{
                'STAT_CODE':'MALFORMED','ITEM_CODE1':'0001000','ITEM_NAME1':'코스피지수',
                'TIME':'20250102','DATA_VALUE':'2500','UNIT_NAME':'지수'}]}}
        with patch.object(module,'get_json',fake):
            with self.assertRaisesRegex(RuntimeError,'identity changed'):
                module.download_series('secret','KOSPI',2025,dt.date(2025,1,31))
    def test_missing_value_never_fabricated(self):
        def fake(_url):return {'RESULT':{'CODE':'INFO-200','MESSAGE':'No data'}}
        with patch.object(module,'get_json',fake):
            self.assertEqual(module.download_series('secret','KOSPI',2025,dt.date(2025,1,31)),[])
    def test_bad_bond_units_fail(self):
        def fake(_url):
            return {'StatisticSearch':{'list_total_count':1,'row':[{
                'STAT_CODE':'817Y002','ITEM_CODE1':'010200000','ITEM_NAME1':'국고채(3년)',
                'TIME':'20250102','DATA_VALUE':'2.7','UNIT_NAME':'억원'}]}}
        with patch.object(module,'get_json',fake):
            with self.assertRaisesRegex(RuntimeError,'unit mismatch'):
                module.download_series('secret','KTB3Y',2025,dt.date(2025,1,31))


if __name__=='__main__':
    unittest.main()
