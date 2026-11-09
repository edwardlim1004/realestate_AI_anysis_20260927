import csv,gzip,io,json,unittest
import build_metro_history as h
class HistoryTests(unittest.TestCase):
 def test_missing_before_start_and_empty_are_distinct(self):
  self.assertEqual('not_available',h.month_record(['26110'],'200601','rent',{},None)['status'])
  self.assertEqual('missing',h.month_record(['26110'],'202611','sale',{},None)['status'])
  key='sale/2026/26110/202611.csv.gz'
  result=h.month_record(['26110'],'202611','sale',{key:{'sha256':'a','rows':0}},lambda *x:gzip.compress('계약년월,원본항목JSON\n'.encode()))
  self.assertEqual('ready',result['status']);self.assertIsNone(result['metrics']['sale']['median_manwon'])
 def test_alias_overlap_never_summed(self):
  files={f'sale/2026/{c}/202611.csv.gz':{'sha256':c,'rows':1} for c in ['27720','47720']}
  result=h.month_record(['27720','47720'],'202611','sale',files,lambda *x:gzip.compress('계약년월,원본항목JSON\n202611,{}\n'.encode()))
  self.assertEqual('alias_review_required',result['status']);self.assertNotIn('metrics',result)
 def test_wrong_month_rejected(self):
  with self.assertRaises(ValueError):h.month_record(['26110'],'202611','sale',{'sale/2026/26110/202611.csv.gz':{'sha256':'a'}},lambda *x:gzip.compress('계약년월\n202610\n'.encode()))
if __name__=='__main__':unittest.main()
