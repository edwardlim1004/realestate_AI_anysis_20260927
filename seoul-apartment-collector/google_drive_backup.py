#!/usr/bin/env python3
# coding: utf-8
"""Cloudflare R2 -> OAuth user's Google Drive, resumable annual CSV backups.

- R2 is read-only; no delete requests to R2 or Google Drive.
- Google drive.file OAuth scope, only self-created folders/files.
- GitHub Secrets bootstrap Google refresh token; token rotation encrypted at rest in private R2.
- Changed years only; Drive metadata checks make uploads idempotent.
"""
import argparse
import base64
import csv
import gzip
import hashlib
import json
import os
import random
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

BASE=Path(__file__).resolve().parent
MANIFEST=BASE/"r2_manifest.json"
REPORT=BASE/"google_drive_backup_report.json"
PREFIX="seoul-apartments/v1/"
TOKEN_KEY="internal/google-drive-backup-refresh-v1.enc"
SCOPE="https://www.googleapis.com/auth/drive.file"
ROOT_NAME="Edward_부동산데이터_R2백업"
KINDS={"sale":("서울아파트매매","매매"),"rent":("서울아파트전월세","전월세")}
VALID=re.compile(r"^(sale|rent)/(\d{4})/(11\d{3})/(\d{6})\.csv\.gz$")
MAX_SRC_BYTES=50*1024*1024
MAX_YEAR_BYTES=1024*1024*1024
MAX_FILES=30000


def env_required(*keys):
    missing=[k for k in keys if not os.environ.get(k)]
    if missing:raise RuntimeError("Missing GitHub Secrets: "+", ".join(missing))


def s3_client():
    import boto3
    from botocore.config import Config
    env_required("R2_ACCOUNT_ID","R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY","R2_BUCKET_NAME")
    return boto3.client("s3",endpoint_url="https://"+os.environ["R2_ACCOUNT_ID"]+".r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],region_name="auto",
        config=Config(retries={"max_attempts":5,"mode":"standard"},connect_timeout=15,read_timeout=60))


def cipher():
    from cryptography.fernet import Fernet
    seed=("edward-gdrive-2026|"+os.environ["GOOGLE_OAUTH_CLIENT_SECRET"]+"|"
          +os.environ["R2_SECRET_ACCESS_KEY"]).encode("utf-8")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(seed).digest()))


def remote_refresh_token(s3,crypto):
    from botocore.exceptions import ClientError
    try:
        result=s3.get_object(Bucket=os.environ["R2_BUCKET_NAME"],Key=TOKEN_KEY)
    except ClientError as exc:
        code=str(exc.response.get("Error",{}).get("Code"))
        if code in ("404","NoSuchKey","NotFound"):
            return os.environ.get("GOOGLE_OAUTH_REFRESH_TOKEN","")
        raise RuntimeError("Encrypted R2 token lookup failed") from None
    try:
        encrypted=result["Body"].read(8192)
        token=crypto.decrypt(encrypted).decode("utf-8")
        if not 8<=len(token)<=2048:raise ValueError()
        return token
    except Exception:
        raise RuntimeError("Encrypted Google token unreadable; check unchanged R2 and Google secrets") from None


def save_refresh_token(s3,crypto,token):
    if not 8<=len(token)<=2048:raise RuntimeError("Invalid token returned")
    s3.put_object(Bucket=os.environ["R2_BUCKET_NAME"],Key=TOKEN_KEY,
                  Body=crypto.encrypt(token.encode("utf-8")),ContentType="application/octet-stream")


def authorized_drive(s3):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    env_required("GOOGLE_OAUTH_CLIENT_ID","GOOGLE_OAUTH_CLIENT_SECRET")
    crypt=cipher()
    refresh=remote_refresh_token(s3,crypt)
    if not refresh:raise RuntimeError("Missing initial GOOGLE_OAUTH_REFRESH_TOKEN secret")
    credentials=Credentials(token=None,refresh_token=refresh,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],scopes=[SCOPE])
    try:
        credentials.refresh(Request())
    except Exception:
        raise RuntimeError("Google OAuth refresh failed: check OAuth consent, publication status and credentials") from None
    if not credentials.token:raise RuntimeError("Google did not issue access token")
    new_refresh=credentials.refresh_token or refresh
    if new_refresh!=refresh or os.environ.get("GOOGLE_BACKUP_SAVE_BOOTSTRAP","1")=="1":
        # Do not acknowledge auth success until the safe long-term token is persisted.
        save_refresh_token(s3,crypt,new_refresh)
    return build("drive","v3",credentials=credentials,cache_discovery=False)


def load_source_manifest():
    manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("bucket")!="edward-seoul-apartment-data" or manifest.get("prefix")!=PREFIX:
        raise ValueError("R2 manifest bucket/prefix mismatch")
    raw=manifest.get("files")
    if not isinstance(raw,dict) or len(raw)>MAX_FILES:
        raise ValueError("Unexpected R2 manifest size")
    output={}
    for key,value in raw.items():
        m=VALID.fullmatch(key)
        if not m:continue
        kind,year,gu,ym=m.groups()
        if year!=ym[:4] or not 1<=int(ym[4:])<=12:continue
        if not isinstance(value,dict):raise ValueError("Invalid manifest metadata")
        sha=value.get("sha256","")
        size=value.get("bytes",0)
        if not isinstance(sha,str) or not re.fullmatch("[0-9a-f]{64}",sha) or not isinstance(size,int) or not 1<=size<=MAX_SRC_BYTES:
            raise ValueError("Invalid R2 scope digest/size: "+key)
        output.setdefault((kind,year),[]).append((key,sha,size))
    return {year:sorted(rows) for year,rows in output.items()}


def fingerprint(entries):
    h=hashlib.sha256()
    for key,sha,size in entries:
        h.update((key+"|"+sha+"|"+str(size)+"\n").encode("utf-8"))
    return h.hexdigest()


def escape_cell(v):
    value=str(v or "")
    return "'"+value if value.lstrip().startswith(("=","+","-","@")) else value


def build_year_csv(s3,entries,out):
    """Download + integrity check each gzip archive; stream data to one annual CSV."""
    bucket=os.environ["R2_BUCKET_NAME"]
    md5=hashlib.md5()
    rows=0;fields=None
    with out.open("w",encoding="utf-8-sig",newline="") as csvout:
        writer=None
        for idx,(key,expected,size) in enumerate(entries):
            src=out.with_name("scope_"+str(idx)+".gz")
            try:
                s3.download_file(bucket,PREFIX+key,str(src))
                if src.stat().st_size!=size:raise ValueError("R2 file size does not match manifest")
                h=hashlib.sha256()
                with src.open("rb") as handle:
                    while True:
                        chunk=handle.read(1024*1024)
                        if not chunk:break
                        h.update(chunk)
                if h.hexdigest()!=expected:raise ValueError("R2 gzip checksum mismatch; no upload")
                with gzip.open(src,"rt",encoding="utf-8-sig",newline="") as readerfile:
                    reader=csv.DictReader(readerfile)
                    if not reader.fieldnames or not all(v in reader.fieldnames for v in ("계약일","자료종류","원본항목JSON")):
                        raise ValueError("Unexpected CSV header")
                    if writer is None:
                        fields=reader.fieldnames
                        writer=csv.DictWriter(csvout,fieldnames=fields)
                        writer.writeheader()
                    elif reader.fieldnames!=fields:
                        raise ValueError("Yearly archive has inconsistent CSV schema")
                    scope_rows=0
                    for record in reader:
                        if None in record:raise ValueError("Invalid CSV columns")
                        writer.writerow({k:escape_cell(v) for k,v in record.items()})
                        rows+=1;scope_rows+=1
                        if csvout.tell()>MAX_YEAR_BYTES or rows>3000000 or scope_rows>300000:
                            raise ValueError("Annual CSV safety size/row limit exceeded")
            finally:
                if src.exists():src.unlink()
    with out.open("rb") as f:
        while True:
            x=f.read(1024*1024)
            if not x:break
            md5.update(x)
    return md5.hexdigest(),rows,out.stat().st_size


def execute(request,retries=4):
    from googleapiclient.errors import HttpError
    for attempt in range(retries):
        try:return request.execute(num_retries=2)
        except HttpError as exc:
            if exc.resp.status not in (429,500,502,503,504) or attempt+1==retries:
                raise RuntimeError("Google Drive API HTTP "+str(exc.resp.status)) from None
            time.sleep(min(25,2**attempt+random.uniform(0,1)))
    raise RuntimeError("Drive API unavailable")


def find_folder(drive,name,parent):
    escaped=name.replace("\\","\\\\").replace("'","\\'")
    q=f"name = '{escaped}' and '{parent}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    files=execute(drive.files().list(q=q,fields="nextPageToken,files(id,name,createdTime)",
             pageSize=100)).get("files",[])
    files.sort(key=lambda f:f.get("createdTime",""))
    return files[0]["id"] if files else None


def ensure_folder(drive,name,parent,create=True):
    found=find_folder(drive,name,parent)
    if found:return found
    if not create:return None
    r=execute(drive.files().create(body={"name":name,
            "mimeType":"application/vnd.google-apps.folder","parents":[parent]},
            fields="id"))
    return r["id"]


def find_annual_file(drive,folder,key):
    q=f"'{folder}' in parents and appProperties has {{ key='edward_key' and value='{key}' }} and trashed=false"
    files=execute(drive.files().list(q=q,fields="nextPageToken,files(id,name,md5Checksum,appProperties,createdTime)",pageSize=100)).get("files",[])
    files.sort(key=lambda f:f.get("createdTime",""))
    return files[0] if files else None


def upload_annual(drive,folder,kind,year,entries,csv_path,checksum,size,rows,old=None):
    from googleapiclient.http import MediaFileUpload
    key=f"{kind}-{year}"
    filename=f"서울아파트_{KINDS[kind][1]}_{year}.csv"
    props={"edward_key":key,"source_fingerprint":fingerprint(entries),
           "md5":checksum,"scope_count":str(len(entries))}
    meta={"name":filename,"description":f"서울 아파트 {KINDS[kind][1]} 실거래자료 연도별 백업; "
      f"{len(entries)}개 구·월 파일, {rows}행. 전체 과거자료 수집 중 부분 데이터일 수 있음.",
      "appProperties":props}
    media=MediaFileUpload(str(csv_path),mimetype="text/csv",resumable=True,chunksize=8*1024*1024)
    if old:
        req=drive.files().update(fileId=old["id"],body=meta,media_body=media,
                                 fields="id,md5Checksum,appProperties,size")
    else:
        meta["parents"]=[folder]
        req=drive.files().create(body=meta,media_body=media,
                                 fields="id,md5Checksum,appProperties,size")
    from googleapiclient.errors import HttpError
    result=None
    for attempt in range(8):
        try:
            while result is None:
                _,result=req.next_chunk(num_retries=2)
            break
        except HttpError as exc:
            if exc.resp.status not in (429,500,502,503,504) or attempt==7:
                raise RuntimeError("Drive upload HTTP "+str(exc.resp.status)) from None
            time.sleep(min(40,2**attempt+random.uniform(0,1)))
    if not result or result.get("md5Checksum")!=checksum or int(result.get("size",0))!=size:
        raise RuntimeError("Google Drive saved file checksum/size verification failed")
    return result


def backup(mode="sync",max_years=12):
    env_required("R2_ACCOUNT_ID","R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY","R2_BUCKET_NAME",
       "GOOGLE_OAUTH_CLIENT_ID","GOOGLE_OAUTH_CLIENT_SECRET")
    archives=load_source_manifest()
    r2=s3_client()
    drive=authorized_drive(r2)
    if mode=="check":
        execute(drive.files().list(pageSize=1,fields="files(id)",q="trashed=false"))
        print("GOOGLE_DRIVE_AUTH_OK; R2_SCOPES="+str(sum(map(len,archives.values()))))
        return {"mode":"check","r2_scopes":sum(map(len,archives.values())),"uploaded_years":0}
    root=ensure_folder(drive,ROOT_NAME,"root")
    folders={kind:ensure_folder(drive,label,root) for kind,(label,_) in KINDS.items()}
    report={"run_utc":datetime.now(timezone.utc).isoformat(),"mode":mode,
            "r2_scopes":sum(map(len,archives.values())),
            "years_found":len(archives),"uploaded_years":0,"skipped_years":0,"events":[]}
    # Recent periods first for useful data; continue older history next daily run.
    for (kind,year),entries in sorted(archives.items(),key=lambda item:(int(item[0][1]),item[0][0]),reverse=True):
        key=f"{kind}-{year}"
        file=find_annual_file(drive,folders[kind],key)
        new_fp=fingerprint(entries)
        old_props=file.get("appProperties",{}) if file else {}
        if file and old_props.get("source_fingerprint")==new_fp and old_props.get("md5") and file.get("md5Checksum")==old_props["md5"]:
            report["skipped_years"]+=1
            continue
        if report["uploaded_years"]>=max_years:break
        with tempfile.TemporaryDirectory(prefix="edward_r2_gdrive_") as tmp:
            target=Path(tmp)/f"{key}.csv"
            md5,rows,bytes_count=build_year_csv(r2,entries,target)
            upload_annual(drive,folders[kind],kind,year,entries,target,md5,bytes_count,rows,file)
        report["events"].append({"year":year,"kind":kind,"rows":rows,
                     "source_scopes":len(entries),"bytes":bytes_count,"result":"verified"})
        report["uploaded_years"]+=1
        print(f"GDRIVE_BACKUP_OK kind={kind} year={year} scopes={len(entries)} rows={rows} bytes={bytes_count}",flush=True)
        time.sleep(1)
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("GDRIVE_BACKUP_RESULT "+json.dumps({k:v for k,v in report.items() if k!="events"},ensure_ascii=False))
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=["check","sync"],default="sync")
    parser.add_argument("--max-years",type=int,default=12)
    args=parser.parse_args()
    if not 1<=args.max_years<=24:parser.error("max-years must be between 1 and 24")
    try:
        backup(args.mode,args.max_years)
        return 0
    except Exception as exc:
        # Secrets, signed URLs, refresh tokens and response bodies are never printed.
        print("GDRIVE_BACKUP_ERROR "+type(exc).__name__+
              ("; "+str(exc) if isinstance(exc,(RuntimeError,ValueError)) else ""),file=sys.stderr)
        return 1


if __name__=="__main__":sys.exit(main())
