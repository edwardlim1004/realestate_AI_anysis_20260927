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

    def upload(self, local_path, relative=None):
        path = Path(local_path)
        relative = relative or path.relative_to(DATA).as_posix()
        digest = self.checksum(path)
        if self.files.get(relative, {}).get("sha256") == digest:
            self.skipped += 1
            return False
        key = PREFIX + relative
        self.client.upload_file(
            str(path),
            self.bucket,
            key,
            ExtraArgs={"ContentType": "application/gzip"},
        )
        # A successful upload is the prerequisite for recording a completed scope.
        self.files[relative] = {
            "sha256": digest,
            "bytes": path.stat().st_size,
        }
        self.uploaded += 1
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
            "r2_scopes": len(self.files),
            "r2_compressed_bytes": sum(int(v.get("bytes", 0)) for v in self.files.values()),
            "r2_objects_uploaded": self.uploaded,
        }


def main():
    archive = R2Storage()
    archive.migrate_legacy()


if __name__ == "__main__":
    main()
