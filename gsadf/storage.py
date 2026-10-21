"""Private R2 primary archive + independent Google Drive backup for GSADF.

Do not store raw observations in Git. All writes are verified before promoting
the R2 latest pointer. Uses existing R2/GDrive credentials and drive.file scope.
"""
import argparse
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

PREFIX = "gsadf/v1/"
SERIES = ("real_hpi", "pir", "ptr")
EXPECTED = tuple(
    f"korea_{name}_quarterly.csv" for name in SERIES
) + tuple(f"{name}_revisions.csv" for name in SERIES)
MAX_SOURCE_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024

def env_required(*keys):
    missing = [key for key in keys if not os.environ.get(key)]
    if missing:
        raise RuntimeError("Missing GitHub Secrets: " + ", ".join(missing))

def s3_client():
    import boto3
    from botocore.config import Config
    env_required("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME")
    return boto3.client("s3",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto", config=Config(retries={"max_attempts":5,"mode":"standard"}))

def missing_object(exc):
    from botocore.exceptions import ClientError
    return isinstance(exc, ClientError) and str(
        exc.response.get("Error", {}).get("Code", "")
    ) in ("404", "NoSuchKey", "NotFound")

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def checked_put(s3, key, blob, content_type, *, immutable=False):
    bucket = os.environ["R2_BUCKET_NAME"]
    digest = sha256(blob)
    try:
        head = s3.head_object(Bucket=bucket, Key=PREFIX+key)
    except Exception as exc:
        if not missing_object(exc): raise
        head = None
    if head is not None and head.get("Metadata", {}).get("sha256") == digest and head.get("ContentLength") == len(blob):
        return "unchanged"
    if immutable and head is not None:
        raise RuntimeError("Immutable archive key collision; refusing overwrite")
    s3.put_object(Bucket=bucket, Key=PREFIX+key, Body=blob,
        ContentType=content_type, Metadata={"sha256":digest})
    verified = s3.head_object(Bucket=bucket, Key=PREFIX+key)
    if verified.get("ContentLength") != len(blob) or verified.get("Metadata", {}).get("sha256") != digest:
        raise RuntimeError("R2 uploaded object failed head verification")
    return "uploaded"

def restore(data_dir):
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    s3 = s3_client()
    bucket = os.environ["R2_BUCKET_NAME"]
    try:
        pointer = s3.get_object(Bucket=bucket, Key=PREFIX+"latest.json")
    except Exception as exc:
        if missing_object(exc):
            print("GSADF_R2_RESTORE first-ever run, no previous verified bundle")
            return []
        raise
    manifest = json.loads(pointer["Body"].read(MAX_SOURCE_BYTES))
    digest = manifest.get("bundleSHA256","")
    key = manifest.get("R2","")
    if not re.fullmatch("[0-9a-f]{64}",digest) or key != PREFIX+"bundles/"+digest+".zip":
        raise RuntimeError("Invalid GSADF latest pointer")
    response = s3.get_object(Bucket=bucket,Key=key)
    bundle = response["Body"].read(MAX_ARCHIVE_BYTES+1)
    if len(bundle)>MAX_ARCHIVE_BYTES or sha256(bundle)!=digest:
        raise RuntimeError("GSADF R2 archive hash mismatch")
    loaded=[]
    with zipfile.ZipFile(io.BytesIO(bundle)) as source:
        for name in EXPECTED:
            archived="data/"+name
            if archived not in source.namelist(): continue
            blob=source.read(archived)
            if len(blob)>MAX_SOURCE_BYTES: raise RuntimeError("Oversize verified GSADF source")
            (data_dir/name).write_bytes(blob)
            loaded.append(name)
    if all((data_dir/f"korea_{name}_quarterly.csv").exists() for name in SERIES):
        from .change_check import fingerprint
        (data_dir/".previous_series_sha256").write_text(fingerprint(data_dir),encoding="ascii")
    print("GSADF_R2_RESTORE",len(loaded),"series/revision files from verified bundle")
    return loaded

def build_bundle(data_dir, result_dir):
    data_dir, result_dir = Path(data_dir), Path(result_dir)
    inputs = []
    for name in EXPECTED:
        source = data_dir/name
        if source.exists():
            inputs.append((source, "data/"+name))
    for name in ("source_manifest.json",):
        source = data_dir/name
        if source.exists(): inputs.append((source,"data/"+name))
    for kind in SERIES:
        source = result_dir/(kind+".json")
        if not source.is_file(): raise RuntimeError("Missing statistical result: "+kind)
        obj = json.loads(source.read_text(encoding="utf-8"))
        if obj.get("approval") != "PENDING_INDEPENDENT_VALIDATION" or obj.get("eligibleForComposite") is not False:
            raise RuntimeError("Unapproved GSADF result must not be archived as valid")
        if obj.get("method",{}).get("MC_repetitions",0) < 2000:
            raise RuntimeError("Monte Carlo repetitions below required 2000")
        inputs.append((source,"results/"+kind+".json"))
    for kind in SERIES:
        versions=sorted((data_dir/"raw").glob(kind+"_*.csv"))
        if not versions: raise RuntimeError("Missing original OECD snapshot: "+kind)
        inputs.append((versions[-1],"raw/"+kind+".csv"))
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=7) as archive:
        for src,arcname in sorted(inputs,key=lambda entry:entry[1]):
            blob=src.read_bytes()
            if len(blob)>MAX_SOURCE_BYTES: raise RuntimeError("Input file unexpectedly large")
            meta=zipfile.ZipInfo(arcname,date_time=(1980,1,1,0,0,0))
            meta.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(meta,blob,compress_type=zipfile.ZIP_DEFLATED)
    payload=buf.getvalue()
    if not 0<len(payload)<=MAX_ARCHIVE_BYTES: raise RuntimeError("Unexpected archive size")
    return payload

def backup_drive(s3, payload, digest):
    """Reuse the project's private OAuth, validate stored bytes/MD5."""
    path = Path(__file__).resolve().parent.parent/"seoul-apartment-collector"
    if not (path/"google_drive_backup.py").exists():
        raise RuntimeError("Missing existing Google Drive integration")
    sys.path.insert(0,str(path))
    from google_drive_backup import authorized_drive, ensure_folder, execute, ROOT_NAME
    from googleapiclient.http import MediaFileUpload
    env_required("GOOGLE_OAUTH_CLIENT_ID","GOOGLE_OAUTH_CLIENT_SECRET")
    drive=authorized_drive(s3)
    folder=ensure_folder(drive,"GSADF",ensure_folder(drive,ROOT_NAME,"root"))
    key=digest[:24]
    query=f"'{folder}' in parents and trashed=false and appProperties has {{ key='gsadf_bundle' and value='{key}' }}"
    found=execute(drive.files().list(q=query,fields="files(id,md5Checksum,size)",pageSize=100)).get("files",[])
    if len(found)>1: raise RuntimeError("Duplicate GSADF Drive archive")
    md5=hashlib.md5(payload).hexdigest()
    if found:
        entry=found[0]
        if entry.get("md5Checksum")==md5 and int(entry.get("size",0))==len(payload):
            return entry["id"]
        raise RuntimeError("Existing Google Drive archive checksum mismatch")
    with tempfile.TemporaryDirectory() as temp:
        f=Path(temp)/("gsadf_"+digest+".zip")
        f.write_bytes(payload)
        meta={"name":"GSADF_"+digest[:16]+".zip", "parents":[folder],
              "description":"Private official OECD historical data and reproducible GSADF experiment",
              "appProperties":{"gsadf_bundle":key}}
        media=MediaFileUpload(str(f),mimetype="application/zip",resumable=True)
        result=execute(drive.files().create(body=meta,media_body=media,
            fields="id,md5Checksum,size"))
    if not result.get("id") or result.get("md5Checksum")!=md5 or int(result.get("size",0))!=len(payload):
        raise RuntimeError("Google Drive backup failed MD5/size verification")
    return result["id"]

def publish(data_dir,result_dir,status_path):
    data_dir, result_dir, status_path = Path(data_dir),Path(result_dir),Path(status_path)
    payload=build_bundle(data_dir,result_dir); digest=sha256(payload)
    s3=s3_client()
    key="bundles/"+digest+".zip"
    bundle_action=checked_put(s3,key,payload,"application/zip",immutable=True)
    drive_id=backup_drive(s3,payload,digest)  # never mark current until backed up
    updated=[]
    for name in EXPECTED:
        src=data_dir/name
        if src.exists():
            action=checked_put(s3,"current/"+name,src.read_bytes(),"text/csv")
            if action=="uploaded": updated.append(name)
    manifest={"schema":"gsadf-archive.v1","timestampUTC":datetime.now(timezone.utc).isoformat(),
        "R2":PREFIX+key,"bundleSHA256":digest,"sizeBytes":len(payload),
        "googleDriveVerified":True,"googleDriveFileId":drive_id,
        "changedCurrentFiles":updated,"compositePromoted":False}
    checked_put(s3,"latest.json",json.dumps(manifest,sort_keys=True).encode(),"application/json")
    status_path.parent.mkdir(parents=True,exist_ok=True)
    status_path.write_text(json.dumps({k:v for k,v in manifest.items() if k!="googleDriveFileId"},indent=2),encoding="utf-8")
    print("GSADF_R2_DRIVE_ARCHIVE_OK",bundle_action,"changed-series",len(updated))
    return manifest

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("operation",choices=["restore","publish"])
    parser.add_argument("--data-dir",default="gsadf/data")
    parser.add_argument("--result-dir",default="gsadf/output")
    parser.add_argument("--status-path",default="gsadf/audit/status.json")
    args=parser.parse_args()
    if args.operation=="restore":restore(args.data_dir)
    else:publish(args.data_dir,args.result_dir,args.status_path)
