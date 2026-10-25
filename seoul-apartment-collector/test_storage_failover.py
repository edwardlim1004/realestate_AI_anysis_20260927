"""Offline failover safety test. No public data requests, real R2 or Google API."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import r2_bridge as bridge
import backfill_progress as audit
import google_drive_backup as annual
import r2_gdrive_failover as failover

REL="sale/2026/11710/202610.csv.gz"
FILE_ID="googleArchive_Aa11Bb22Cc33"


class FakeS3:
    def __init__(self):self.sent=[]
    def upload_file(self,file,bucket,key,ExtraArgs=None):
        self.sent.append(key)


class GoodDriveArchive:
    def __init__(self,r2):
        self.uploads=0
    def upload(self,rel,path,digest,old_file_id=None):
        assert rel==REL
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest
        assert old_file_id in (None,FILE_ID)
        return FILE_ID


class BadDriveArchive:
    def __init__(self,r2):pass
    def upload(self,*a,**kw):
        raise RuntimeError("Google raw failover upload checksum mismatch")


def fake_archive():
    a=bridge.R2Storage.__new__(bridge.R2Storage)
    a.client=FakeS3()
    a.bucket="edward-seoul-apartment-data"
    a.files={}
    a.uploaded=0
    a.skipped=0
    a._r2_bytes=0
    a.drive_archived=0
    a._drive_archive=None
    a._account_budget=SimpleNamespace(reserve=lambda *a:None)
    return a


def check_restart_accounting(root,creds):
    """R2 objects retained during Drive failover still occupy space next run."""
    cap=1024*1024
    data=root/"restart.csv.gz"
    original=gzip.compress(b"original scope",mtime=0)
    data.write_bytes(original)
    retained=len(original)
    other="rent/2026/11110/202610.csv.gz"
    store=fake_archive()
    store.files={
        REL:{"sha256":hashlib.sha256(original).hexdigest(),
             "bytes":retained,"storage":"r2"},
        other:{"sha256":"a"*64,"bytes":cap-retained,"storage":"r2"},
    }
    store._r2_bytes=cap
    manifest=root/"restart_manifest.json"
    modules={
        "boto3":SimpleNamespace(client=lambda *a,**kw:FakeS3()),
        "botocore.config":SimpleNamespace(Config=lambda **kw:None),
    }
    with patch.object(bridge,"MANIFEST",manifest), \
         patch.dict(os.environ,creds), \
         patch.dict(sys.modules,modules), \
         patch.object(failover,"DriveRawArchive",GoodDriveArchive):
        data.write_bytes(gzip.compress(bytes(range(256))*4,mtime=0))
        store.upload(data,relative=REL)
        assert store.files[REL]["retained_r2_bytes"]==retained
        store.save_manifest()

        # Construct the next collector from the saved manifest, not shared memory.
        restarted=bridge.R2Storage()
        assert restarted.stats()["r2_compressed_bytes"]==cap
        data.write_bytes(gzip.compress(b"second update"+bytes(range(256)),mtime=0))
        restarted.upload(data,relative=REL)
        restarted.save_manifest()
        restarted=bridge.R2Storage()
        assert restarted.stats()["r2_compressed_bytes"]==cap
        assert restarted.files[REL]["retained_r2_bytes"]==retained

        # A fresh scope must use Drive: retained R2 bytes cannot become free space.
        fresh="sale/2026/11110/202610.csv.gz"
        with patch.object(restarted,"_to_google_drive",return_value=True) as route:
            restarted.upload(data,relative=fresh)
            assert route.call_args.args[1]==fresh
        assert not restarted.client.sent


def main():
    with tempfile.TemporaryDirectory() as work:
        root=Path(work)
        payload=gzip.compress(b"sample scope",mtime=0)
        data=root/"raw.csv.gz"
        data.write_bytes(payload)
        assert not audit.completeness({})["completed"]
        with patch.dict(os.environ,{"R2_STORAGE_SOFT_CAP_BYTES":str(1024*1024)}):
            store=fake_archive()
            assert store.upload(data,relative=REL)
            assert store.files[REL]["storage"]=="r2"
            assert store.stats()["r2_scopes"]==1
            assert not store.upload(data,relative=REL)
            assert len(store.client.sent)==1

        # Raise the source R2 usage just below the configured 1 MiB test soft cap.
        creds={"R2_GDRIVE_FALLBACK_ENABLED":"true",
               "R2_STORAGE_SOFT_CAP_BYTES":str(1024*1024),
               "GOOGLE_OAUTH_CLIENT_ID":"nonprod_dummy",
               "GOOGLE_OAUTH_CLIENT_SECRET":"nonprod_dummy",
               "GOOGLE_OAUTH_REFRESH_TOKEN":"nonprod_dummy",
               "R2_ACCOUNT_ID":"f"*32,
               "R2_ACCESS_KEY_ID":"nonprod_dummy",
               "R2_SECRET_ACCESS_KEY":"nonprod_dummy",
               "R2_BUCKET_NAME":"edward-seoul-apartment-data"}
        payload2=gzip.compress(b"CHANGED scope",mtime=0)
        data.write_bytes(payload2)
        store._r2_bytes=1024*1024
        with patch.dict(os.environ,creds),patch.object(failover,"DriveRawArchive",GoodDriveArchive):
            store.upload(data,relative=REL)
        assert store.files[REL]["storage"]=="gdrive",store.files
        assert store.files[REL]["drive_file_id"]==FILE_ID
        assert store.stats()["gdrive_scopes"]==1
        assert store.stats()["r2_scopes"]==0
        assert store.stats()["r2_compressed_bytes"]==1024*1024  # old R2 object was NOT deleted
        assert store.client.sent==[bridge.PREFIX+REL]

        # Missing Drive file-id or short checksum cannot count as a verified scope.
        manifest_entry=store.files[REL]
        assert not audit.completeness({REL:{"sha256":manifest_entry["sha256"],
                       "bytes":manifest_entry["bytes"],"storage":"gdrive"}})["verified_manifest_scopes"]==1
        # Patch the 11000-scope expected keys to a single test input.
        with patch.object(audit,"expected_keys",lambda:iter([REL])):
            assert audit.completeness({REL:manifest_entry})["completed"]
            assert not audit.completeness({REL:{**manifest_entry,"drive_file_id":"invalid!"}})["completed"]
            assert not audit.completeness({REL:{**manifest_entry,"storage":"unknown"}})["completed"]

        # On a failed Drive upload, the existing verified manifest and original
        # R2 object must be unchanged, so the next run safely retries.
        data.write_bytes(gzip.compress(b"NEW unverified scope",mtime=0))
        old=store.files[REL].copy()
        with patch.dict(os.environ,creds),patch.object(failover,"DriveRawArchive",BadDriveArchive):
            store._drive_archive=None
            try:store.upload(data,relative=REL)
            except RuntimeError as exc:assert "checksum" in str(exc)
            else:raise AssertionError("Failed Google upload was accepted")
        assert store.files[REL]==old
        assert len(store.client.sent)==1

        # Mixed manifest: existing old R2 entries have no 'storage' tag.
        r2_rel="rent/2026/11710/202610.csv.gz"
        example={REL:manifest_entry,r2_rel:{"sha256":"a"*64,"bytes":13}}
        manifest=root/"manifest.json"
        manifest.write_text(json.dumps({"bucket":"edward-seoul-apartment-data",
                                       "prefix":bridge.PREFIX,"files":example}))
        with patch.object(annual,"MANIFEST",manifest):
            entries=annual.load_source_manifest()
        assert entries[("sale","2026")][0][3]==FILE_ID
        assert len(entries[("rent","2026")][0])==3
        assert annual.fingerprint(entries[("sale","2026")])

        with patch.dict(os.environ,{"R2_STORAGE_SOFT_CAP_BYTES":str(1024*1024)}):
            store2=fake_archive();store2._r2_bytes=1024*1024
            with patch.object(store2,"fallback_enabled",return_value=False):
                try:store2.upload(data,relative=REL)
                except RuntimeError as exc:assert "failover" in str(exc).lower()
                else:raise AssertionError("R2 cap exceeded with no failover was accepted")
                assert store2.files=={}
        check_restart_accounting(root,creds)
    print("PASS: soft-cap routing; R2 not deleted; retained R2 bytes survive restart; SHA256/MD5 precondition; verified manifest; failed upload safe stop; mixed backup support")


if __name__=="__main__":main()
