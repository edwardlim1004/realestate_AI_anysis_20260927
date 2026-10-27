import unittest
from audit_repaired_capital import reuse_evidence


class EvidenceTests(unittest.TestCase):
    def test_changed_bytes_identity_or_semantics_require_live_reread(self):
        result={'status':'ok','rows':2,'content_sha256':'b'*64}
        meta={'sha256':'a'*64,'bytes':123,'storage':'gdrive','drive_file_id':'original-id','rows':2,'content_sha256':'b'*64}
        self.assertTrue(reuse_evidence('scope',result,meta,meta.copy()))
        for change in ({'sha256':'c'*64},{'bytes':124},{'drive_file_id':'other-id'},
                       {'storage':'r2'},{'rows':3},{'content_sha256':'c'*64}):
            self.assertFalse(reuse_evidence('scope',result,meta,{**meta,**change}))
        self.assertFalse(reuse_evidence('scope',None,meta,meta))


if __name__=='__main__':unittest.main(verbosity=2)
