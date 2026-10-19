"""Offline tests: no real Cloudflare, Google Drive, token or F-drive access."""
import csv
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import google_drive_backup as b


def gz_sample(kind,date):
    f=io.BytesIO()
    with gzip.GzipFile(fileobj=f,mode="wb",mtime=0) as z:
        with io.TextIOWrapper(z,encoding="utf-8-sig",newline="") as s:
            w=csv.writer(s)
            w.writerow(["계약일","자료종류","원본항목JSON"])
            w.writerow([date,"아파트 매매" if kind=="sale" else "아파트 전월세",'=HYPERLINK("unsafe","click")'])
    return f.getvalue()


class FakeR2:
    def __init__(self,entries):self.entries=entries;self.downloads=0
    def download_file(self,bucket,key,destination):
        assert bucket=="edward-seoul-apartment-data"
        self.downloads+=1
        Path(destination).write_bytes(self.entries[key])


def main():
    blobs={}
    scope_rows={}
    for kind,ym,date in [("sale","202610","2026-10-18"),("sale","200601","2006-01-01"),("rent","202610","2026-10-18")]:
        rel=f"{kind}/{ym[:4]}/11710/{ym}.csv.gz"
        data=gz_sample(kind,date)
        blobs[b.PREFIX+rel]=data
        scope_rows[rel]={"sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data)}
    manifest={"bucket":"edward-seoul-apartment-data","prefix":b.PREFIX,"files":scope_rows}
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)
        source=p/"r2_manifest.json"
        source.write_text(json.dumps(manifest),encoding="utf-8")
        with patch.object(b,"MANIFEST",source):
            annuals=b.load_source_manifest()
            assert set(annuals)=={("sale","2026"),("sale","2006"),("rent","2026")}
            assert b.fingerprint(annuals[("sale","2026")])==b.fingerprint(annuals[("sale","2026")])
            r2=FakeR2(blobs)
            year_file=p/"sale-2026.csv"
            with patch.dict(os.environ,{"R2_BUCKET_NAME":"edward-seoul-apartment-data"}):
                md5,n,size=b.build_year_csv(r2,annuals[("sale","2026")],year_file)
            assert n==1 and size>0 and md5==hashlib.md5(year_file.read_bytes()).hexdigest()
            with year_file.open("r",encoding="utf-8-sig",newline="") as f:
                row=list(csv.DictReader(f))[0]
                assert row["원본항목JSON"].startswith("'=")
            corrupted=scope_rows.copy()
            k="sale/2026/11710/202610.csv.gz"
            corrupted[k]={"sha256":"f"*64,"bytes":scope_rows[k]["bytes"]}
            try:
                with patch.dict(os.environ,{"R2_BUCKET_NAME":"edward-seoul-apartment-data"}):
                    b.build_year_csv(r2,[(k,corrupted[k]["sha256"],corrupted[k]["bytes"])],p/"bad.csv")
            except ValueError as exc:
                assert "checksum" in str(exc)
            else:raise AssertionError("R2 corrupted archive was accepted")

            remote={}
            sent=[]
            fake_env={"R2_ACCOUNT_ID":"1"*32,
                      "R2_ACCESS_KEY_ID":"fake","R2_SECRET_ACCESS_KEY":"fake",
                      "R2_BUCKET_NAME":"edward-seoul-apartment-data",
                      "GOOGLE_OAUTH_CLIENT_ID":"fake","GOOGLE_OAUTH_CLIENT_SECRET":"fake"}
            def find_fake(drive,folder,key):
                old=remote.get(key)
                if old:return old
                return None
            def upload_fake(drive,folder,kind,year,entries,csvpath,checksum,nbytes,rows,old):
                key=f"{kind}-{year}"
                remote[key]={"id":key,"appProperties":{"source_fingerprint":b.fingerprint(entries),
                                  "md5":checksum},"md5Checksum":checksum}
                sent.append(key)
                return remote[key]
            report_path=p/"report.json"
            with patch.dict(os.environ,fake_env),patch.object(b,"MANIFEST",source),patch.object(b,"REPORT",report_path),\
                 patch.object(b,"s3_client",return_value=r2),patch.object(b,"authorized_drive",return_value=object()),\
                 patch.object(b,"ensure_folder",side_effect=lambda d,name,parent:create_folder(name,parent)),\
                 patch.object(b,"find_annual_file",side_effect=find_fake),\
                 patch.object(b,"upload_annual",side_effect=upload_fake),patch.object(b.time,"sleep"):
                result=b.backup("sync",max_years=2)
                assert result["uploaded_years"]==2,result
                assert len(remote)==2,remote
                result=b.backup("sync",max_years=3)
                assert result["uploaded_years"]==1,result
                result=b.backup("sync",max_years=3)
                assert result["uploaded_years"]==0 and result["skipped_years"]==3,result
                assert len(sent)==3
        print("PASS: manifest validation, SHA256 integrity, CSV formula safety, resume, no duplicate Drive backups")


def create_folder(name,parent):
    return "folder-"+name

if __name__=="__main__":main()
