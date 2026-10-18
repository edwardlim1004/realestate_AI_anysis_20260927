#!/usr/bin/env python3
# coding: utf-8
"""Read-only Cloudflare R2 -> Windows F: incremental apartment CSV exporter.

No incoming connections, no administrator permissions, no Git credentials on PC.
Requires boto3 and keyring; token must be OBJECT READ ONLY, bucket-scoped.
"""
import argparse
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from datetime import datetime
from getpass import getpass
from contextlib import contextmanager

SERVICE="EdwardSeoulApartmentR2ReadOnly"
BUCKET="edward-seoul-apartment-data"
PREFIX="seoul-apartments/v1/"
DEST=Path(r"F:\01.LIM EDWARD\00. 아빠폴더(미래준비 및 취미)\2.부동산\2.부동산\1.서울아파트 매매전월세 거래 정보")
KINDS={"sale":("서울아파트매매","매매"),"rent":("서울아파트전월세","전월세")}
DISTRICTS={"11110","11140","11170","11200","11215","11230","11260","11290","11305",
"11320","11350","11380","11410","11440","11470","11500","11530","11545",
"11560","11590","11620","11650","11680","11710","11740"}
OBJ_RE=re.compile(r"^(sale|rent)/(\d{4})/(\d{5})/(\d{6})\.csv\.gz$")
MAX_OBJECT_BYTES=50*1024*1024
MIN_FREE_BYTES=2*1024*1024*1024
STATE_VERSION=1
USER_DIR=Path(os.environ.get("LOCALAPPDATA",Path.home()/".local"/"share"))/"EdwardSeoulAptSync"
CFG=USER_DIR/"config.json"
STATE=USER_DIR/"sync_state.json"
LOG_DIR=USER_DIR/"logs"


def log(message):
    line=datetime.now().strftime("%Y-%m-%d %H:%M:%S")+" "+str(message)
    print(line,flush=True)
    try:
        LOG_DIR.mkdir(parents=True,exist_ok=True)
        with (LOG_DIR/("sync-"+datetime.now().strftime("%Y%m%d")+".log")).open("a",encoding="utf-8") as h:
            h.write(line+"\n")
    except OSError:
        pass


def write_json_atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+".pending")
    try:
        tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        os.replace(tmp,path)
    finally:
        if tmp.exists():tmp.unlink()


def read_json(path,default):
    if not path.exists():return default
    data=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data,dict):raise ValueError("Invalid local state/config")
    return data


def config():
    return read_json(CFG,{})


def client_from_windows_vault():
    import boto3
    import keyring
    access=keyring.get_password(SERVICE,"r2_access_key_id")
    secret=keyring.get_password(SERVICE,"r2_secret_access_key")
    account=config().get("account_id","")
    if not access or not secret or not re.fullmatch(r"[a-fA-F0-9]{32}",account):
        raise RuntimeError("PC R2 read-only credentials unavailable; run setup first")
    from botocore.config import Config
    return boto3.client("s3",endpoint_url="https://"+account+".r2.cloudflarestorage.com",
        aws_access_key_id=access,aws_secret_access_key=secret,region_name="auto",
        config=Config(retries={"max_attempts":3,"mode":"standard"},connect_timeout=10,read_timeout=45))


def setup():
    if os.name!="nt":
        raise RuntimeError("Setup requires Windows Credential Manager.")
    print("Cloudflare R2: create a DIFFERENT token with Object Read Only for this bucket.")
    print("Do NOT enter the GitHub R2 write token here.")
    account=input("Cloudflare Account ID (32 hexadecimal characters): ").strip()
    if not re.fullmatch(r"[a-fA-F0-9]{32}",account):
        raise ValueError("Account ID must be 32 hex characters")
    key_id=getpass("Read-only R2 Access Key ID (hidden): ").strip()
    secret=getpass("Read-only R2 Secret Access Key (hidden): ").strip()
    if len(key_id)<8 or len(secret)<8:raise ValueError("Invalid credential length")
    import keyring
    keyring.set_password(SERVICE,"r2_access_key_id",key_id)
    keyring.set_password(SERVICE,"r2_secret_access_key",secret)
    write_json_atomic(CFG,{"account_id":account,"bucket":BUCKET,
        "output_directory":str(DEST),"security":"read-only R2 token in Windows Credential Manager"})
    try:
        client_from_windows_vault().list_objects_v2(Bucket=BUCKET,Prefix=PREFIX,MaxKeys=1)
    except Exception as exc:
        raise RuntimeError("R2 read-only connection test failed; verify token, account, bucket") from None
    log("SETUP_OK: read-only R2 connection verified. Credentials stored in Windows vault.")


@contextmanager
def singleton():
    USER_DIR.mkdir(parents=True,exist_ok=True)
    lockfile=USER_DIR/"sync.lock"
    f=open(lockfile,"a+b")
    try:
        f.seek(0);f.write(b"0");f.flush();f.seek(0)
        if os.name=="nt":
            import msvcrt
            try:msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
            except OSError:raise RuntimeError("Another sync is already running") from None
        else:
            import fcntl
            try:fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError:raise RuntimeError("Another sync is already running") from None
        yield
    finally:
        if os.name=="nt":
            import msvcrt
            try:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
            except OSError:pass
        else:
            import fcntl
            fcntl.flock(f.fileno(),fcntl.LOCK_UN)
        f.close()


def parse_key(key):
    if not key.startswith(PREFIX):return None
    rel=key[len(PREFIX):]
    m=OBJ_RE.fullmatch(rel)
    if not m:return None
    kind,year,gu,ym=m.groups()
    if gu not in DISTRICTS or year!=ym[:4] or not ("2006"<=year<="2100"):
        return None
    return rel,kind,year,gu,ym


def list_remote(client):
    output={}
    for page in client.get_paginator("list_objects_v2").paginate(Bucket=BUCKET,Prefix=PREFIX,PaginationConfig={"PageSize":500}):
        for entry in page.get("Contents",[]):
            item=parse_key(entry["Key"])
            if item is None:continue
            rel,kind,year,gu,ym=item
            size=int(entry["Size"])
            if not 1<=size<=MAX_OBJECT_BYTES:
                raise RuntimeError("Unexpected R2 object size for "+rel)
            output[rel]={"etag":str(entry.get("ETag","")).strip('"'),"size":size}
            if len(output)>20000:raise RuntimeError("Unexpectedly high object count")
    return output


def verify_gz(path):
    expanded=0
    with gzip.open(path,"rt",encoding="utf-8-sig",newline="") as f:
        reader=csv.reader(f)
        header=next(reader,None)
        if not header or not all(col in header for col in ("계약일","자료종류","원본항목JSON")):
            raise ValueError("Invalid CSV header")
        for row in reader:
            expanded+=sum(len(c) for c in row)+len(row)*4
            if expanded>100*1024*1024:
                raise ValueError("Unexpected gzip expanded size")
            if len(row)!=len(header):raise ValueError("CSV column count mismatch")
    return header


def download_one(client,key,output,size,max_rate_kbps=2048):
    import time
    output.parent.mkdir(parents=True,exist_ok=True)
    if output.is_symlink():raise RuntimeError("Refusing to overwrite a symlink")
    tmp=output.with_name(output.name+".part")
    if tmp.exists():tmp.unlink()
    try:
        response=client.get_object(Bucket=BUCKET,Key=key)
        if int(response.get("ContentLength",-1))!=size:
            raise IOError("Remote object size changed while downloading")
        h=hashlib.sha256()
        count=0
        start=time.monotonic()
        with tmp.open("xb") as writer:
            while True:
                chunk=response["Body"].read(128*1024)
                if not chunk:break
                writer.write(chunk);h.update(chunk);count+=len(chunk)
                if count>size:raise IOError("Object larger than expected")
                if max_rate_kbps:
                    wait=count/(max_rate_kbps*1024)-(time.monotonic()-start)
                    if wait>0:time.sleep(wait)
        if count!=size:raise IOError("Incomplete object download")
        verify_gz(tmp)
        os.replace(tmp,output)
        return h.hexdigest()
    finally:
        if tmp.exists():tmp.unlink()


def safe_cell(value):
    # CSV opened in Excel: never interpret untrusted source text as a formula.
    value=str(value or "")
    if value.lstrip().startswith(("=","+","-","@")):
        return "'"+value
    return value


def annual_output(root,kind,year):
    folder,label=KINDS[kind]
    return root/folder/(f"서울아파트_{label}_R2_{year}.csv")


def build_year(root,kind,year,remote,state):
    rels=sorted(r for r in remote if parse_key(PREFIX+r)[1:3]==(kind,year))
    if not rels:return None
    cache=root/"_R2_작업데이터"/"원본압축"
    sources=[cache/r for r in rels]
    if not all(p.is_file() for p in sources):
        log(f"SKIP_YEAR {kind} {year}: some scope files not yet downloaded")
        return None
    output=annual_output(root,kind,year)
    if output.is_symlink():raise RuntimeError("Refusing output symlink")
    ownership=state.setdefault("generated_years",{})
    output_key=f"{kind}/{year}"
    if output.exists() and ownership.get(output_key)!=str(output):
        raise RuntimeError("Existing manual CSV must not be overwritten: "+str(output))
    output.parent.mkdir(parents=True,exist_ok=True)
    tmp=output.with_name(output.name+".pending")
    count=0
    try:
        with tmp.open("w",encoding="utf-8-sig",newline="") as f:
            writer=None
            for src in sources:
                with gzip.open(src,"rt",encoding="utf-8-sig",newline="") as inp:
                    reader=csv.DictReader(inp)
                    if writer is None:
                        if not reader.fieldnames:raise ValueError("Empty header")
                        header=reader.fieldnames
                        writer=csv.DictWriter(f,fieldnames=header,extrasaction="raise")
                        writer.writeheader()
                    elif reader.fieldnames!=header:
                        raise ValueError("Source schema mismatch")
                    for line in reader:
                        writer.writerow({k:safe_cell(v) for k,v in line.items()})
                        count+=1
                        if count>2000000:raise RuntimeError("Annual row safety limit")
        os.replace(tmp,output)
    finally:
        if tmp.exists():tmp.unlink()
    ownership[output_key]=str(output)
    log(f"CSV_YEAR_OK {kind} {year}: {count} rows")
    return count


def sync(client,root=DEST,max_mb=256,rate_kbps=2048,state_path=STATE):
    root=Path(root)
    if os.name=="nt" and not Path(root.anchor).exists():
        raise RuntimeError("F: drive is not mounted; no folders changed.")
    root.mkdir(parents=True,exist_ok=True)
    free=shutil.disk_usage(root).free
    if free<MIN_FREE_BYTES:raise RuntimeError("Less than 2GB disk free; safe stop")
    state=read_json(state_path,{"version":STATE_VERSION,"objects":{},"generated_years":{}})
    if state.get("version")!=STATE_VERSION:raise ValueError("Unknown state format")
    remote=list_remote(client)
    objects=state.setdefault("objects",{})
    cache=root/"_R2_작업데이터"/"원본압축"
    changes=set()
    total=0;downloaded=0;skipped=0
    budget=max(1,int(max_mb))*1024*1024
    for rel,meta in sorted(remote.items()):
        local=cache/rel
        old=objects.get(rel,{})
        same=(local.is_file() and not local.is_symlink() and
              local.stat().st_size==meta["size"] and
              old.get("etag")==meta["etag"] and old.get("size")==meta["size"])
        if same:skipped+=1;continue
        if total+meta["size"]>budget:
            log("DOWNLOAD_LIMIT_REACHED; remaining scopes deferred")
            break
        if shutil.disk_usage(root).free < MIN_FREE_BYTES+meta["size"]*3:
            log("LOW_DISK_SAFE_STOP")
            break
        digest=download_one(client,PREFIX+rel,local,meta["size"],rate_kbps)
        objects[rel]={**meta,"sha256":digest}
        kind,year=parse_key(PREFIX+rel)[1:3]
        changes.add((kind,year))
        total+=meta["size"];downloaded+=1
        write_json_atomic(state_path,state)
    # A missing yearly output is rebuilt automatically, but unrelated CSVs are never modified.
    years={(parse_key(PREFIX+r)[1],parse_key(PREFIX+r)[2]) for r in remote}
    years.update(changes)
    rebuilt=0
    for kind,year in sorted(years):
        if (kind,year) in changes or not annual_output(root,kind,year).exists():
            result=build_year(root,kind,year,remote,state)
            if result is not None:
                rebuilt+=1
                write_json_atomic(state_path,state)
    state["last_sync_at"]=datetime.now().isoformat(timespec="seconds")
    state["last_inventory_count"]=len(remote)
    state["last_download_count"]=downloaded
    state["last_rebuilt_years"]=rebuilt
    write_json_atomic(state_path,state)
    log(f"SUCCESS remote_scopes={len(remote)} downloaded={downloaded} skipped={skipped} built_years={rebuilt} downloaded_MB={total/1048576:.2f}")
    return {"remote_scopes":len(remote),"downloaded":downloaded,"rebuilt_years":rebuilt}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("command",choices=("setup","sync","status"))
    parser.add_argument("--max-mb",type=int,default=256)
    parser.add_argument("--rate-kbps",type=int,default=2048)
    args=parser.parse_args()
    try:
        if args.command=="setup":
            setup();return 0
        if args.command=="status":
            print(json.dumps(read_json(STATE,{"message":"No completed sync yet"}),
                             ensure_ascii=False,indent=2))
            return 0
        if not 1<=args.max_mb<=1024:raise ValueError("--max-mb must be 1..1024")
        if not 64<=args.rate_kbps<=8192:raise ValueError("--rate-kbps must be 64..8192")
        with singleton():
            sync(client_from_windows_vault(),DEST,args.max_mb,args.rate_kbps)
        return 0
    except Exception as exc:
        # Never log object credentials, signed URLs or secrets.
        log("ERROR "+type(exc).__name__+"; check Windows credential, network, storage and R2 bucket")
        return 1

if __name__=="__main__":sys.exit(main())
