#!/usr/bin/env python3
"""No-credential Kakao completion message and encrypted token logic tests."""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import kakao_self_alert as k


class Store:
    def __init__(self):
        self.data={}
    def put_object(self,**kwargs):
        self.data[kwargs["Key"]]=bytes(kwargs["Body"])
    def get_object(self,**kwargs):
        key=kwargs["Key"]
        if key not in self.data:
            from botocore.exceptions import ClientError
            raise ClientError({"Error":{"Code":"NoSuchKey","Message":"not found"}},"GetObject")
        class Body:
            def __init__(self,blob):self.blob=blob
            def read(self,n=8192):return self.blob
        return {"Body":Body(self.data[key])}


def main():
    env={
        "KAKAO_REST_API_KEY":"test_api_key",
        "KAKAO_CLIENT_SECRET":"local_unit_test_secret",
        "KAKAO_REFRESH_TOKEN":"r0_refresh_token_sample",
        "R2_ACCOUNT_ID":"f"*32,
        "R2_ACCESS_KEY_ID":"local_test",
        "R2_SECRET_ACCESS_KEY":"encrypted_storage_unit_test_key",
        "R2_BUCKET_NAME":"edward-seoul-apartment-data",
        "GITHUB_REPOSITORY":"edwardlim1004/realestate_AI_anysis_20260927",
        "GH_TOKEN":"dummy_unit_test",
    }
    store=Store()
    sent=[]
    with patch.dict(os.environ,{'KAKAO_COMPLETION_ISSUE_NUMBER':'15'}), \
         patch.object(k,'github_request',return_value={'number':15,'title':k.ISSUE_TITLE}) as request:
        assert k.find_completion_issue()==15
        assert request.call_count==1
        assert request.call_args.args[0].endswith('/issues/15')
    with patch.dict(os.environ,{'KAKAO_COMPLETION_ISSUE_NUMBER':'15'}), \
         patch.object(k,'github_request',side_effect=[k.NotificationError('Service HTTP 404 on api.github.com'),{'number':15,'title':k.ISSUE_TITLE}]), \
         patch.object(k.time,'sleep'):
        assert k.find_completion_issue()==15
    with patch.dict(os.environ,{'KAKAO_COMPLETION_ISSUE_NUMBER':'15'}), \
         patch.object(k,'github_request',return_value={'number':15,'title':'Different issue'}):
        try:k.find_completion_issue()
        except k.NotificationError:pass
        else:raise AssertionError('Mismatched completion issue accepted')
    with patch.dict(os.environ,env,clear=True), patch.object(k,"renew_access_token",return_value=("access_test","r1_rotated_refresh_token_sample")):
        status=k.notify("test",storage=store,send=lambda token,message:sent.append((token,message)))
        assert status=="sent",status
        assert len(sent)==1 and "[테스트]" in sent[0][1]
        assert k.TOKEN_OBJECT in store.data
        assert b"r1_rotated_refresh_token_sample" not in store.data[k.TOKEN_OBJECT]
        assert k.get_refresh_token(store,k.token_cipher_secret())=="r1_rotated_refresh_token_sample"
        assert k.payload("test")["link"]["web_url"]=="https://edwardlim1004.github.io/realestate_AI_anysis_20260927/"
        try:k.payload("x"*201)
        except ValueError:pass
        else:raise AssertionError("Overlong message accepted")
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"progress.json"
            with patch.object(k,"PROGRESS",file):
                file.write_text('{"completed":false,"verified_manifest_scopes":200}',encoding="utf-8")
                assert k.notify("complete",storage=store,send=lambda *_:1)=="skipped"
                file.write_text('{"completed":true,"verified_manifest_scopes":11000}',encoding="utf-8")
                with patch.object(k,"find_completion_issue",return_value=20),patch.object(k,"has_sent_comment",return_value=True):
                    assert k.notify("complete",storage=store,send=lambda *_:1)=="already_sent"
                events=[]
                with patch.object(k,"find_completion_issue",return_value=20),patch.object(k,"has_sent_comment",return_value=False),patch.object(k,"record_sent_comment",side_effect=lambda i:events.append(("comment",i))):
                    assert k.notify("complete",storage=store,send=lambda token,msg:events.append(("sent",msg)))=="sent"
                    assert events[0][0]=="sent" and events[1]==("comment",20)
    print("PASS: OAuth token encryption/rotation, text template, incomplete skip, idempotency, completion message")

if __name__=="__main__":main()
