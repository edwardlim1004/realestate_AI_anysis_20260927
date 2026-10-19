#!/usr/bin/env python3
# coding: utf-8
"""Explicit one-file Google raw archival probe; never modify the source manifest.

Runs only from the manual GitHub workflow. The raw file is an existing verified
R2 source; upload is idempotent and does not delete or change source objects.
"""
import hashlib
import json
import os
import tempfile
from pathlib import Path

from google_drive_backup import MANIFEST, PREFIX, s3_client, MAX_SRC_BYTES
from r2_gdrive_failover import DriveRawArchive, KEY_RE


def main():
    manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))
    entries=manifest.get("files",{})
    candidate=None
    for key,entry in sorted(entries.items(),reverse=True):
        if (KEY_RE.fullmatch(key) and key.startswith("sale/")
            and entry.get("storage","r2")=="r2"
            and 1<=int(entry.get("bytes",0))<=min(MAX_SRC_BYTES,512*1024)):
            candidate=(key,entry)
            break
    if not candidate:raise RuntimeError("No verified R2 source suitable for test")
    rel,meta=candidate
    s3=s3_client()
    with tempfile.TemporaryDirectory(prefix="r2_gdrive_probe_") as tmp:
        dest=Path(tmp)/"probe.csv.gz"
        s3.download_file(os.environ["R2_BUCKET_NAME"],PREFIX+rel,str(dest))
        data=dest.read_bytes()
        if len(data)!=meta["bytes"] or hashlib.sha256(data).hexdigest()!=meta["sha256"]:
            raise RuntimeError("R2 source checksum invalid; Google probe not attempted")
        result=DriveRawArchive(s3).upload(rel,dest,meta["sha256"])
        if not result:raise RuntimeError("Google Drive did not return a verified object id")
    print("R2_GDRIVE_RAW_PROBE_SUCCESS: verified R2 source copied to private Google Drive archive")
    print("R2 source and source manifest unchanged; existing annual CSV remains usable")


if __name__=="__main__":main()
