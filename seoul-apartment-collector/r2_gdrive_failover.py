#!/usr/bin/env python3
# coding: utf-8
"""Verified last-resort Cloudflare R2 -> Google Drive raw gzip failover.

Google Drive objects are app-created and private. The caller commits an object to
the source manifest ONLY after Google Drive responds with matching MD5 and size.
No Cloudflare object is deleted, and there is no automatic migration of old data.
"""
import hashlib
import os
import random
import re
import time
from pathlib import Path

from google_drive_backup import ROOT_NAME, authorized_drive, ensure_folder, execute

FOLDER_NAME="원본월별압축_자동전환"
SCOPE_MARKER="edward_archive_scope"
KEY_RE=re.compile(r"^(sale|rent)/(\d{4})/((?:11|30|41)\d{3})/(\d{6})\.csv\.gz$")
MAX_BYTES=50*1024*1024


class DriveRawArchive:
    def __init__(self,r2):
        # Reuse the SAME Google OAuth credentials and R2 encrypted refresh token as
        # the independently tested annual CSV backup.
        self.drive=authorized_drive(r2)
        root=ensure_folder(self.drive,ROOT_NAME,"root")
        self.folder=ensure_folder(self.drive,FOLDER_NAME,root)

    def lookup(self,rel):
        q=(f"'{self.folder}' in parents and trashed = false and "
           f"appProperties has {{ key='{SCOPE_MARKER}' and value='{rel}' }}")
        found=execute(self.drive.files().list(q=q,pageSize=100,
            fields="nextPageToken,files(id,name,md5Checksum,size,parents,appProperties,createdTime)")).get("files",[])
        found.sort(key=lambda item:item.get("createdTime",""))
        if len(found)>1:
            raise RuntimeError("Duplicate raw Google Drive scope; manual reconciliation required")
        return found[0] if found else None

    def upload(self,rel,src,expected_sha,old_file_id=None):
        from googleapiclient.http import MediaFileUpload
        from googleapiclient.errors import HttpError
        if not KEY_RE.fullmatch(rel):
            raise ValueError("Unsafe source relative path")
        src=Path(src)
        size=src.stat().st_size
        if not 1<=size<=MAX_BYTES:raise ValueError("Unexpected raw scope size")
        sha=hashlib.sha256()
        md5=hashlib.md5()
        with src.open("rb") as inp:
            for buf in iter(lambda:inp.read(1024*1024),b""):
                sha.update(buf);md5.update(buf)
        if sha.hexdigest()!=expected_sha:
            raise ValueError("Raw scope changed before failover upload")
        existing=self.lookup(rel)
        if old_file_id and existing and old_file_id!=existing["id"]:
            raise RuntimeError("Google archive id does not match manifest")
        if old_file_id and not existing:
            raise RuntimeError("Previously archived Google scope is missing; refusing silent duplicate")
        checksum=md5.hexdigest()
        if existing and existing.get("md5Checksum")==checksum and int(existing.get("size",0))==size:
            return existing["id"]
        metadata={"name":rel.replace("/","_"),"description":"Edward Seoul/Gyeonggi/Daejeon apartment public transaction raw compressed scope",
            "appProperties":{SCOPE_MARKER:rel,"sha256":expected_sha}}
        from storage_usage import check_google_capacity
        check_google_capacity(self.drive,size)
        media=MediaFileUpload(str(src),mimetype="application/gzip",resumable=True,chunksize=8*1024*1024)
        if existing:
            req=self.drive.files().update(fileId=existing["id"],body=metadata,
                media_body=media,fields="id,md5Checksum,size,appProperties")
        else:
            metadata["parents"]=[self.folder]
            req=self.drive.files().create(body=metadata,media_body=media,
                fields="id,md5Checksum,size,appProperties")
        result=None
        for attempt in range(7):
            try:
                while result is None:
                    _,result=req.next_chunk(num_retries=2)
                break
            except HttpError as exc:
                if exc.resp.status not in (429,500,502,503,504) or attempt==6:
                    raise RuntimeError("Google raw failover upload failed") from None
                time.sleep(min(35,2**attempt+random.uniform(0,1)))
        if not result or not result.get("id") or result.get("md5Checksum")!=checksum or int(result.get("size",0))!=size:
            raise RuntimeError("Google Drive raw scope upload checksum mismatch; manifest unchanged")
        return result["id"]


def is_enabled():
    return os.environ.get("R2_GDRIVE_FALLBACK_ENABLED","").strip().lower()=="true"


def have_credentials():
    return bool(all(os.environ.get(k) for k in (
        "GOOGLE_OAUTH_CLIENT_ID","GOOGLE_OAUTH_CLIENT_SECRET","GOOGLE_OAUTH_REFRESH_TOKEN",
        "R2_ACCOUNT_ID","R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY","R2_BUCKET_NAME")))

