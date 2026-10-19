"""R2 S3-compatible object storage. Credentials are read from environment only.

This module migrates already committed monthly CSV.gz archives and maintains a
small Git-tracked manifest for subsequent GitHub Actions runs.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
MANIFEST = HERE / "r2_manifest.json"
PREFIX = "seoul-apartments/v1/"


class R2Storage:
    def __init__(self):
        required = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME")
        missing = [key for key in required if not os.getenv(key)]
        if missing:
            raise RuntimeError("R2 Secrets missing: " + ", ".join(missing))
        import boto3
        from botocore.config import Config
        self.bucket = os.environ["R2_BUCKET_NAME"]
        self.client = boto3.client(
            "s3",
            endpoint_url="https://" + os.environ["R2_ACCOUNT_ID"] + ".r2.cloudflarestorage.com",
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
            config=Config(
                retries={"max_attempts": 5, "mode": "standard"},
                connect_timeout=15,
                read_timeout=60,
            ),
        )
        if MANIFEST.exists():
            manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
            self.files = manifest.get("files", {})
            if not isinstance(self.files, dict):
                raise RuntimeError("Invalid manifest; refusing to collect.")
        else:
            self.files = {}
        self.uploaded = 0
        self.skipped = 0
        self._r2_bytes = sum(int(v.get("bytes",0)) for v in self.files.values()
                             if v.get("storage","r2")=="r2")
        self.drive_archived = 0
        self._drive_archive = None

    @staticmethod
    def relpath(kind, district, ym):
        return f"{kind}/{ym[:4]}/{district}/{ym}.csv.gz"

    def has_scope(self, kind, district, ym):
        return self.relpath(kind, district, ym) in self.files

    @staticmethod
    def checksum(path):
        h = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def fallback_enabled(self):
        from r2_gdrive_failover import is_enabled, have_credentials
        return is_enabled() and have_credentials()

    def _to_google_drive(self, path, relative, digest, size, old):
        from r2_gdrive_failover import DriveRawArchive
        if not self.fallback_enabled():
            raise RuntimeError("R2 safety limit reached; Google Drive verified failover is not configured")
        if self._drive_archive is None:
            self._drive_archive = DriveRawArchive(self.client)
        file_id=self._drive_archive.upload(relative,path,digest,
             old_file_id=old.get("drive_file_id") if old.get("storage")=="gdrive" else None)
        # Only count a scope as completed AFTER Drive verified its MD5 and byte count.
        self.files[relative]={"sha256":digest,"bytes":size,
                               "storage":"gdrive","drive_file_id":file_id}
        if old.get("storage","r2")=="r2":
            self._r2_bytes-=int(old.get("bytes",0))
        self.uploaded+=1
        self.drive_archived+=1
        return True

    def upload(self,local_path,relative=None):
        path=Path(local_path)
        relative=relative or path.relative_to(DATA).as_posix()
        digest=self.checksum(path)
        old=self.files.get(relative,{})
        if old.get("sha256")==digest:
            self.skipped+=1
            return False
        size=path.stat().st_size
        if not 1<=size<=50*1024*1024:
            raise ValueError("Unexpected scope file size")
        from r2_gdrive_failover import KEY_RE
        if not KEY_RE.fullmatch(relative):
            raise ValueError("Invalid scope relative name")
        new_r2_bytes=self._r2_bytes-(int(old.get("bytes",0))
                       if old.get("storage","r2")=="r2" else 0)+size
        safety_cap=int(os.environ.get("R2_STORAGE_SOFT_CAP_BYTES",str(8*1024*1024*1024)))
        if not 1024*1024 <= safety_cap <= 10*1024*1024*1024*1024:
            raise ValueError("R2 safety cap outside allowed range")
        if new_r2_bytes>safety_cap or old.get("storage")=="gdrive":
            print("R2_GDRIVE_FAILOVER_BEGIN",relative,flush=True)
            result=self._to_google_drive(path,relative,digest,size,old)
            print("R2_GDRIVE_FAILOVER_VERIFIED",relative,flush=True)
            return result
        try:
            self.client.upload_file(str(path),self.bucket,PREFIX+relative,
                                    ExtraArgs={"ContentType":"application/gzip"})
        except Exception as exc:
            # Other failures remain errors; do not misclassify transient outages
            # or credential failures as an R2 storage quota condition.
            from botocore.exceptions import ClientError
            if not isinstance(exc,ClientError):raise
            code=str(exc.response.get("Error",{}).get("Code",""))
            status=exc.response.get("ResponseMetadata",{}).get("HTTPStatusCode")
            if code not in ("QuotaExceeded","StorageQuotaExceeded","InsufficientStorage") and status!=507:
                raise
            print("R2_STORAGE_QUOTA_FAILOVER",relative,flush=True)
            return self._to_google_drive(path,relative,digest,size,old)
        self._r2_bytes=new_r2_bytes
        self.files[relative]={"sha256":digest,"bytes":size,"storage":"r2"}
        self.uploaded+=1
        return True

    def migrate_legacy(self):
        """Upload all local previously committed scope files before new collecting."""
        if not DATA.exists():
            return
        for path in sorted(DATA.rglob("*.csv.gz")):
            self.upload(path)
        self.save_manifest()
        print(
            f"R2_MIGRATION uploaded={self.uploaded} skipped={self.skipped} scopes={len(self.files)}",
            flush=True,
        )

    def save_manifest(self):
        data = {
            "schema": 1,
            "bucket": self.bucket,
            "prefix": PREFIX,
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            "files": dict(sorted(self.files.items())),
        }
        tmp = MANIFEST.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(MANIFEST)

    def stats(self):
        return {
            "total_scopes":len(self.files),
            "r2_scopes":sum(1 for v in self.files.values() if v.get("storage","r2")=="r2"),
            "gdrive_scopes":sum(1 for v in self.files.values() if v.get("storage")=="gdrive"),
            "r2_compressed_bytes":self._r2_bytes,
            "r2_objects_uploaded":self.uploaded-self.drive_archived,
            "gdrive_objects_uploaded":self.drive_archived,
        }


def main():
    archive = R2Storage()
    archive.migrate_legacy()


if __name__ == "__main__":
    main()
