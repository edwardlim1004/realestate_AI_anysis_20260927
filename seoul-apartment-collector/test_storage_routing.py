"""R2 budget failures cannot mark unverified Drive files as collected."""
from datetime import datetime
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gsadf import storage as gs
from storage_budget import StorageBudgetExceeded
from test_storage_failover import fake_archive,GoodDriveArchive,BadDriveArchive,REL
import r2_gdrive_failover as failover
import google_drive_backup as drive_backup


def denied(*args):raise StorageBudgetExceeded('8 GB guard')


class RoutingTests(unittest.TestCase):
    def test_apartment_guard_uses_verified_drive_and_rolls_back_on_failure(self):
        for success in (True,False):
            with self.subTest(success=success),tempfile.TemporaryDirectory() as tmp:
                store=fake_archive();store._account_budget=SimpleNamespace(reserve=denied)
                source=Path(tmp)/'scope.gz';source.write_bytes(gzip.compress(b'sample source'))
                provider=GoodDriveArchive if success else BadDriveArchive
                with patch.object(store,'fallback_enabled',return_value=True),patch.object(failover,'DriveRawArchive',provider):
                    if success:
                        store.upload(source,relative=REL)
                        self.assertEqual('gdrive',store.files[REL]['storage'])
                    else:
                        with self.assertRaises(RuntimeError):store.upload(source,relative=REL)
                        self.assertEqual({},store.files)
                self.assertEqual([],store.client.sent)

    def test_gsadf_guard_failure_needs_verified_drive_before_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);status=root/'status.json';calls=[]
            def put(client,key,blob,content_type,**kwargs):
                calls.append((key,kwargs))
                if key.startswith('bundles/'):raise StorageBudgetExceeded('capacity')
                self.assertEqual('latest.json',key);self.assertTrue(kwargs['control'])
                return 'uploaded'
            with patch.object(gs,'build_bundle',return_value=b'archive'), \
                 patch.object(gs,'s3_client',return_value=object()),patch.object(gs,'checked_put',side_effect=put), \
                 patch.object(gs,'backup_drive',return_value='drive_verified_Aa11'):
                result=gs.publish(root,root,status)
            self.assertEqual('gdrive',result['storage']);self.assertIsNone(result['R2'])
            self.assertFalse(result['compositePromoted']);self.assertEqual(2,len(calls))
            status.unlink();calls.clear()
            with patch.object(gs,'build_bundle',return_value=b'archive'), \
                 patch.object(gs,'s3_client',return_value=object()),patch.object(gs,'checked_put',side_effect=put), \
                 patch.object(gs,'backup_drive',side_effect=RuntimeError('Drive failed')):
                with self.assertRaises(RuntimeError):gs.publish(root,root,status)
            self.assertFalse(status.exists());self.assertEqual(1,len(calls))

    def test_gsadf_drive_restore_checks_sha_before_extracting(self):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as archive:archive.writestr('data/korea_real_hpi_quarterly.csv','date,value\n2020-Q1,1\n')
        blob=out.getvalue()
        class Downloader:
            def __init__(self,output,request,**kwargs):self.output=output
            def next_chunk(self,**kwargs):self.output.write(blob);return None,True
        class Drive:
            def files(self):return self
            def get_media(self,**kwargs):return object()
        for valid in (True,False):
            with self.subTest(valid=valid),tempfile.TemporaryDirectory() as tmp:
                pointer={'storage':'gdrive','R2':None,'googleDriveFileId':'drive_verified_Aa11',
                         'bundleSHA256':hashlib.sha256(blob).hexdigest() if valid else 'a'*64}
                class Client:
                    def get_object(self,**kwargs):
                        self_key=kwargs['Key']
                        if self_key!=gs.PREFIX+'latest.json':raise AssertionError('No raw R2 download expected')
                        return {'Body':io.BytesIO(json.dumps(pointer).encode())}
                with patch.dict(os.environ,{'R2_BUCKET_NAME':'test'}),patch.object(gs,'s3_client',return_value=Client()), \
                     patch.object(drive_backup,'authorized_drive',return_value=Drive()), \
                     patch.dict(sys.modules,{'googleapiclient.http':SimpleNamespace(MediaIoBaseDownload=Downloader)}):
                    if valid:
                        self.assertEqual(['korea_real_hpi_quarterly.csv'],gs.restore(tmp))
                        self.assertTrue((Path(tmp)/'korea_real_hpi_quarterly.csv').exists())
                    else:
                        with self.assertRaises(RuntimeError):gs.restore(tmp)
                        self.assertFalse((Path(tmp)/'korea_real_hpi_quarterly.csv').exists())


if __name__=='__main__':unittest.main(verbosity=2)
