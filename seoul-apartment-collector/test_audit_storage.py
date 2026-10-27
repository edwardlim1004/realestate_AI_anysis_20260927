"""Corruption, omitted pages/rows, empty scopes and rent types in live audits."""
import csv
import gzip
import hashlib
import io
import json
import unittest

import audit_storage as audit
import collect
from incremental import content_hash


def fixture(records,kind='rent'):
    stream=io.StringIO(newline='')
    writer=csv.DictWriter(stream,fieldnames=collect.FIELDS,lineterminator='\n')
    writer.writeheader()
    for raw in records:writer.writerow(collect.row(kind,'11110','202610',raw))
    payload=gzip.compress(stream.getvalue().encode('utf-8-sig'),mtime=0)
    return payload,{'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest(),
                    'rows':len(records),'content_sha256':content_hash(records)}


class AuditTests(unittest.TestCase):
    def test_rent_split_identical_records_and_real_zero(self):
        common={'dealYear':'2026','dealMonth':'10','dealDay':'25','sggCd':'11110'}
        rows=[{**common,'monthlyRent':'0'},{**common,'monthlyRent':'50'},{**common,'monthlyRent':'50'}]
        payload,meta=fixture(rows)
        result=audit.inspect_scope('rent/2026/11110/202610.csv.gz',meta,payload)
        self.assertEqual({'jeonse':1,'monthly':2},result['transactions'])
        self.assertEqual(1,result['identical_extra_rows'])
        payload,meta=fixture([])
        self.assertEqual(0,audit.inspect_scope('rent/2026/11110/202610.csv.gz',meta,payload)['rows'])

    def test_corruption_row_loss_and_wrong_scope_fail(self):
        rows=[{'dealYear':'2026','dealMonth':'10','dealDay':'25','sggCd':'11110','monthlyRent':'0'}]
        payload,meta=fixture(rows)
        with self.assertRaises(ValueError):audit.inspect_scope('rent/2026/11110/202610.csv.gz',meta,payload[:-1]+b'x')
        with self.assertRaises(ValueError):audit.inspect_scope('rent/2026/11110/202610.csv.gz',{**meta,'rows':2},payload)
        with self.assertRaises(ValueError):audit.inspect_scope('rent/2026/11110/202609.csv.gz',meta,payload)
        with self.assertRaises(ValueError):audit.inspect_scope('rent/2026/11140/202610.csv.gz',meta,payload)

    def test_invalid_rent_cannot_count_as_jeonse(self):
        payload,meta=fixture([{'dealYear':'2026','dealMonth':'10','dealDay':'25','monthlyRent':''}])
        with self.assertRaises(ValueError):audit.inspect_scope('rent/2026/11110/202610.csv.gz',meta,payload)


if __name__=='__main__':unittest.main(verbosity=2)
