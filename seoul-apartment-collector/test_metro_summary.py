import csv
from datetime import date
import gzip
import hashlib
import io
from pathlib import Path
import unittest
from unittest.mock import patch
import archive_reader
import build_metro_summary as summary

class SummaryTests(unittest.TestCase):
    def test_reporting_lag_cutoff(self):
        self.assertEqual('202609',summary.cutoff(date(2026,11,6)))
        self.assertEqual('202610',summary.cutoff(date(2026,12,1)))

    def test_multiplicity_cancel_and_monthly_split(self):
        row={'전용면적(㎡)':'84','거래금액(만원)':'10,000','보증금(만원)':'5000','월세금(만원)':'0'}
        expensive={**row,'거래금액(만원)':'30000'}
        cancelled={**expensive,'해제사유발생일':'20261101'}
        actual=summary.summarize([row,row,expensive,cancelled],'sale')
        self.assertEqual((3,1,10000,20000),(actual['rows'],actual['identical_extra_rows'],actual['median_manwon'],actual['distinct_row_median_manwon']))
        rent={**row,'보증금(만원)':'0','월세금(만원)':'90'}
        self.assertEqual(1,summary.summarize([row,rent],'jeonse')['rows'])
        self.assertEqual(90,summary.summarize([row,rent],'monthly')['monthly_rent_median_manwon'])

    def test_unverified_never_reads_private_price(self):
        report={'cities':{c:{'verified':False,'percent':0} for c in summary.METRO_REGIONS}}
        def reject(*args):raise AssertionError('No source reads before verification')
        result=summary.build(report,{},reject)
        self.assertTrue(all(not c['districts'] for c in result['cities'].values()))

    def test_alias_overlap_blocks_district(self):
        row={'계약년월':'202609','전용면적(㎡)':'84','거래금액(만원)':'10000'}
        def payload(ym):
            f=io.StringIO();w=csv.DictWriter(f,fieldnames=list(row));w.writeheader();w.writerow({**row,'계약년월':ym});return gzip.compress(f.getvalue().encode())
        files={f'{k}/{ym[:4]}/{code}/{ym}.csv.gz':{'sha256':'a'} for code in ('27720','47720') for k in ('sale','rent') for ym in [summary.shift('202609',i) for i in range(-11,1)]}
        report={'cities':{'daegu':{'verified':True,'percent':100,'manifest_fingerprint':'fp'}}}
        with patch.object(summary,'METRO_REGIONS',{'daegu':{'27720':'군위군','47720':'군위군'}}),patch.object(summary.collect,'today',return_value=date(2026,11,6)):
            out=summary.build(report,files,lambda k,e:payload(k.split('/')[-1][:6]))
        district=out['cities']['daegu']['districts'][0]
        self.assertEqual('alias_review_required',district['status'])
        self.assertNotIn('sale',district)

class ReaderTests(unittest.TestCase):
    def test_drive_lazy_and_verified_reader_shared(self):
        obj=archive_reader.VerifiedArchiveReader(s3=object())
        def download(s3,spec,path,drive=None):path.write_bytes(b'good')
        with patch.object(archive_reader,'authorized_drive',return_value='drive') as auth,patch.object(archive_reader,'download_verified_source',side_effect=download) as verified:
            self.assertEqual(b'good',obj('sale/2026/11110/202601.csv.gz',{'sha256':'a','bytes':4}))
            auth.assert_not_called()
            e={'storage':'gdrive','drive_file_id':'private-file','sha256':'a','bytes':4}
            obj('sale/2026/11110/202601.csv.gz',e);obj('sale/2026/11110/202602.csv.gz',e)
            auth.assert_called_once()
            self.assertEqual('private-file',verified.call_args.args[1][3])
        with self.assertRaises(ValueError):obj('x',{'storage':'unknown','sha256':'a','bytes':4})

    def test_checksum_failure_propagates(self):
        obj=archive_reader.VerifiedArchiveReader(s3=object())
        with patch.object(archive_reader,'download_verified_source',side_effect=ValueError('checksum')):
            with self.assertRaises(ValueError):obj('x',{'sha256':'bad','bytes':4})

if __name__=='__main__':unittest.main()
