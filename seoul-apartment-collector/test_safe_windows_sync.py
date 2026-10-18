"""No-network tests for the R2 Windows read-only sync and 11,000-scope completion checker."""
import csv
import gzip
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
spec=importlib.util.spec_from_file_location("safe_r2_sync",HERE/"windows"/"r2_windows_sync.py")
sync=importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)
import backfill_progress as progress


class FakeBody:
    def __init__(self,data):self.obj=io.BytesIO(data)
    def read(self,n):return self.obj.read(n)

class FakePaginator:
    def __init__(self,data):self.data=data
    def paginate(self,**kwargs):
        return [{"Contents":[{"Key":key,"Size":len(v),"ETag":'"'+str(len(v))+'"'} for key,v in self.data.items()]}]

class FakeR2:
    def __init__(self,data):self.data=data;self.calls=0
    def get_paginator(self,method):
        assert method=="list_objects_v2"
        return FakePaginator(self.data)
    def get_object(self,Bucket,Key):
        self.calls+=1
        data=self.data[Key]
        return {"ContentLength":len(data),"Body":FakeBody(data)}


def gz_data():
    stream=io.BytesIO()
    with gzip.GzipFile(fileobj=stream,mode="wb",mtime=0) as z:
        with io.TextIOWrapper(z,encoding="utf-8-sig",newline="") as csvstream:
            writer=csv.writer(csvstream)
            writer.writerow(["계약일","자료종류","원본항목JSON"])
            writer.writerow(["2026-09-02","아파트 매매",'{"aptNm":"=HYPERLINK(1)"}'])
    return stream.getvalue()


def main():
    assert len(list(progress.expected_keys()))==11000
    assert not progress.completeness({})["completed"]
    all_good={key:{"sha256":"a"*64,"bytes":100} for key in progress.expected_keys()}
    good=progress.completeness(all_good)
    assert good["completed"] and good["verified_manifest_scopes"]==11000
    assert not progress.completeness(dict(list(all_good.items())[:-1]))["completed"]
    assert sync.parse_key(sync.PREFIX+"sale/2026/11710/202609.csv.gz")
    assert sync.parse_key(sync.PREFIX+"sale/2026/00000/202609.csv.gz") is None
    assert sync.parse_key(sync.PREFIX+"../secret.txt") is None
    assert sync.safe_cell("=1+2")=="'=1+2"
    with tempfile.TemporaryDirectory() as work:
        root=Path(work)/"F-drive-mock"
        local_state=Path(work)/"sync_state.json"
        rel="sale/2026/11710/202609.csv.gz"
        body=gz_data()
        api=FakeR2({sync.PREFIX+rel:body})
        with patch.object(sync,"MIN_FREE_BYTES",1):
            result=sync.sync(api,root,max_mb=5,rate_kbps=0,state_path=local_state)
            assert result["downloaded"]==1, result
            output=sync.annual_output(root,"sale","2026")
            assert output.is_file() and output.stat().st_size>0
            assert api.calls==1
            assert sync.sync(api,root,max_mb=5,rate_kbps=0,state_path=local_state)["downloaded"]==0
            assert api.calls==1,api.calls
            with output.open("r",encoding="utf-8-sig",newline="") as f:
                rows=list(csv.DictReader(f))
            assert len(rows)==1 and rows[0]["계약일"]=="2026-09-02"
            # Do not overwrite manual files not marked as program-owned.
            local_state.unlink()
            try:
                sync.sync(api,root,max_mb=5,rate_kbps=0,state_path=local_state)
            except RuntimeError as e:
                assert "manual CSV" in str(e)
            else:
                raise AssertionError("Manual CSV was overwritten")
            # Malformed downloaded CSV cannot replace a verified archive.
            api2=FakeR2({sync.PREFIX+rel:b"not a gzip file"})
            local_state.unlink()
            archived=root/"_R2_작업데이터"/"원본압축"/rel
            archived.unlink()
            try:
                sync.sync(api2,root,max_mb=5,rate_kbps=0,state_path=local_state)
            except Exception:
                pass
            else:
                raise AssertionError("Invalid gzip accepted")
            assert not archived.exists()
    print("PASS: 11000-scope audit; safe R2 parser; unchanged skip; annual CSV; manual preservation; corrupt download blocked")

if __name__=="__main__":main()
