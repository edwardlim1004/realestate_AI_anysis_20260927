import copy
import unittest
from complete_source_audit import resume,source_keys
from incremental import content_hash


class API:
    calls=0;limit=1200
    def __init__(self,raw):self.raw=raw;self.requested=[]
    def fetch(self,kind,gu,ym):
        self.calls+=1;self.requested.append((kind,gu,ym));return self.raw


class ResumeTests(unittest.TestCase):
    def test_exact_cursor_and_no_false_success_on_source_change(self):
        results=[{'scope':'rent/2011/41195/201101.csv.gz','status':'ok','rows':0,'content_sha256':content_hash([])},
                 {'scope':'rent/2011/41590/201101.csv.gz','status':'ok','rows':0,'content_sha256':content_hash([])},
                 {'scope':'sale/2006/11110/200601.csv.gz','status':'ok','rows':1,'content_sha256':content_hash([{'aptNm':'A'}])}]
        report={'storage_complete':True,'expected_scopes':3,'source_checks':{'requested':3,'checked':1,'pending':2,'requests':1,'errors':[],'different_scopes':[]}}
        api=API([]);api.limit=1
        partial=resume(copy.deepcopy(report),results,api)
        self.assertEqual([('rent','41590','201101')],api.requested)
        self.assertFalse(partial['passed']);self.assertEqual(1,partial['source_checks']['pending'])
        final=resume(copy.deepcopy(partial),results,API([{'aptNm':'A'}]))
        self.assertTrue(final['passed']);self.assertEqual(0,final['source_checks']['pending'])
        mismatch=resume(copy.deepcopy(partial),results,API([{'aptNm':'changed'}]))
        self.assertFalse(mismatch['passed'])
        self.assertEqual(['sale/2006/11110/200601.csv.gz'],mismatch['source_checks']['different_scopes'])


if __name__=='__main__':unittest.main(verbosity=2)
