#!/usr/bin/env python3
# coding: utf-8
"""Send a single owner-only Kakao My Chat alert when Seoul apartment backfill completes.

No Kakao credentials or tokens are ever written to Git or logged.
A Kakao refresh token (re)issued by Kakao is encrypted in the existing private R2 bucket.
The first token is bootstrapped through KAKAO_REFRESH_TOKEN GitHub Actions Secret.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
PROGRESS = BASE / "backfill_progress.json"
TOKEN_OBJECT = "internal/kakao-selfchat-refresh-v1.enc"
HISTORY_SENT_OBJECT = "internal/kakao-five-year-trade-history-sent-v1"
ISSUE_TITLE = "서울 아파트 실거래 과거자료 수집 완료 (2026-10)"
COMMENT_MARK = "<!-- edward-kakao-sent:seoul-history-202610 -->"
LINK = "https://edwardlim1004.github.io/realestate_AI_anysis_20260927/"
KAKAO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
TOKEN_URL = "https://kauth.kakao.com/oauth/token"
GITHUB_API = "https://api.github.com"


class NotificationError(Exception):
    pass


def request_json(url, data=None, headers=None, method=None):
    req = urllib.request.Request(
        url, data=data, method=method or ("POST" if data is not None else "GET"),
        headers={"User-Agent": "EdwardSeoulApt-Completion-Alert/1.0", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as res:
            raw=res.read(1024 * 1024)
            result=json.loads(raw.decode("utf-8"))
            if not isinstance(result, (dict,list)):
                raise NotificationError("Unexpected JSON response")
            return result
    except urllib.error.HTTPError as exc:
        # Do not expose response bodies or auth headers in CI logs.
        raise NotificationError(f"Service HTTP {exc.code} on {urllib.parse.urlparse(url).hostname}") from None
    except (TimeoutError, urllib.error.URLError) as exc:
        raise NotificationError("Service network error; inspect DNS/connection") from None


def token_cipher_secret():
    from cryptography.fernet import Fernet
    a=os.environ["KAKAO_CLIENT_SECRET"]
    b=os.environ["R2_SECRET_ACCESS_KEY"]
    seed=hashlib.sha256(("edward-seoul-kakao-v1|"+a+"|"+b).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(seed))


def r2_client():
    import boto3
    from botocore.config import Config
    account=os.environ["R2_ACCOUNT_ID"]
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
        config=Config(retries={"max_attempts":3,"mode":"standard"},connect_timeout=10,read_timeout=25),
    )


def get_refresh_token(storage, decryptor):
    from botocore.exceptions import ClientError
    try:
        response=storage.get_object(Bucket=os.environ["R2_BUCKET_NAME"], Key=TOKEN_OBJECT)
    except ClientError as error:
        code=str(error.response.get("Error",{}).get("Code",""))
        if code in ("NoSuchKey","404","NotFound"):
            return os.environ.get("KAKAO_REFRESH_TOKEN","").strip()
        raise NotificationError("Unable to load encrypted refresh token from R2") from None
    try:
        value=decryptor.decrypt(response["Body"].read(8192)).decode("utf-8")
        if not value or len(value)>2048:raise ValueError()
        return value
    except Exception:
        raise NotificationError("Encrypted token invalid or encryption secrets changed") from None


def save_refresh_token(storage, encryptor, refresh_token):
    if not refresh_token or len(refresh_token)>2048:
        raise NotificationError("Invalid rotated refresh token")
    payload=encryptor.encrypt(refresh_token.encode("utf-8"))
    storage.put_object(
        Bucket=os.environ["R2_BUCKET_NAME"],Key=TOKEN_OBJECT,Body=payload,
        ContentType="application/octet-stream",
        ServerSideEncryption="AES256",
    )


def renew_access_token(refresh_token):
    body={"grant_type":"refresh_token","client_id":os.environ["KAKAO_REST_API_KEY"],
          "refresh_token":refresh_token,"client_secret":os.environ["KAKAO_CLIENT_SECRET"]}
    response=request_json(TOKEN_URL,urllib.parse.urlencode(body).encode("utf-8"),
                          {"Content-Type":"application/x-www-form-urlencoded;charset=utf-8"})
    access=response.get("access_token")
    if not isinstance(access,str) or not access:
        raise NotificationError("Kakao refresh response has no access token")
    rotated=response.get("refresh_token")
    if rotated is not None and (not isinstance(rotated,str) or len(rotated)<10):
        raise NotificationError("Invalid rotated token from Kakao")
    return access,rotated


def payload(text):
    if not 1<=len(text)<=200:raise ValueError("Kakao message must be 1..200 characters")
    return {
        "object_type":"text",
        "text":text,
        "link":{"web_url":LINK,"mobile_web_url":LINK},
        "button_title":"부동산 분석 사이트",
    }


def send_to_me(access_token,text):
    data=urllib.parse.urlencode({"template_object":json.dumps(payload(text),ensure_ascii=False)}).encode("utf-8")
    response=request_json(KAKAO_URL,data,{
        "Authorization":"Bearer "+access_token,
        "Content-Type":"application/x-www-form-urlencoded;charset=utf-8",
    })
    if response.get("result_code") != 0:
        raise NotificationError("Kakao message API did not confirm success")
    return True


def github_request(path, method="GET", data=None):
    headers={
        "Authorization":"Bearer "+os.environ["GH_TOKEN"],
        "Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28",
    }
    payload_bytes=json.dumps(data).encode("utf-8") if data is not None else None
    if payload_bytes:headers["Content-Type"]="application/json"
    return request_json(GITHUB_API+path,payload_bytes,headers,method)


def find_completion_issue():
    repo=os.getenv("GITHUB_REPOSITORY","edwardlim1004/realestate_AI_anysis_20260927")
    supplied=os.getenv('KAKAO_COMPLETION_ISSUE_NUMBER','').strip()
    if supplied:
        if not supplied.isdecimal() or int(supplied)<1:
            raise NotificationError('Invalid completion issue number')
        # The creation step already resolved this issue. Avoid a second list
        # search immediately after creation, when list results may still lag.
        for attempt in range(4):
            try:
                issue=github_request(f'/repos/{repo}/issues/{int(supplied)}')
                break
            except NotificationError as exc:
                if 'HTTP 404' not in str(exc) or attempt==3:raise
                time.sleep(2**attempt)
        if issue.get('title')!=ISSUE_TITLE or issue.get('pull_request'):
            raise NotificationError('Completion issue does not match verified collection')
        return int(supplied)
    for page in range(1,7):
        issues=github_request(f"/repos/{repo}/issues?state=all&per_page=100&page={page}")
        for issue in issues:
            if issue.get("title")==ISSUE_TITLE and not issue.get("pull_request"):
                return issue["number"]
        if len(issues)<100:break
    raise NotificationError("Completion issue not found; cannot send until issue is created")


def has_sent_comment(issue):
    repo=os.getenv("GITHUB_REPOSITORY","edwardlim1004/realestate_AI_anysis_20260927")
    for page in range(1,11):
        comments=github_request(f"/repos/{repo}/issues/{issue}/comments?per_page=100&page={page}")
        if any(COMMENT_MARK in x.get("body","") for x in comments):return True
        if len(comments)<100:return False
    raise NotificationError("Cannot conclusively verify prior notifications")


def record_sent_comment(issue):
    repo=os.getenv("GITHUB_REPOSITORY","edwardlim1004/realestate_AI_anysis_20260927")
    github_request(f"/repos/{repo}/issues/{issue}/comments",method="POST",data={
        "body":COMMENT_MARK+"\n카카오톡 '나와의 채팅' 수집 완료 알림 발송 성공 (API 응답 확인)."
    })


def five_year_history_summary():
    root=BASE.parent/"trade-details"/"history"
    try:
        report=json.loads((root/"build-report.json").read_text(encoding="utf-8"))
        index=json.loads((root/"index.json").read_text(encoding="utf-8"))
    except (OSError,ValueError):
        print("KAKAO_SKIP: five-year public archive report unavailable")
        return None
    entries=report.get("regions",[])
    months=report.get("months",[])
    if len(months)!=60 or len(index.get("regions",{}))!=61 or len(entries)!=122:
        print("KAKAO_SKIP: five-year archive scope is incomplete")
        return None
    if any(int(x.get("missing_scopes",1))>0 for x in entries):
        print("KAKAO_SKIP: five-year archive has missing source scopes")
        return None
    if {(x.get("region"),x.get("kind")) for x in entries} != {
        (region,kind) for region in index["regions"] for kind in ("sale","rent")
    }:
        print("KAKAO_SKIP: five-year archive region/type coverage mismatch")
        return None
    return report["start_month"],report["end_month"]


def notify(mode,storage=None,refresh=None,send=send_to_me):
    if mode not in ("complete","test","refresh","history5y"):
        raise ValueError("Invalid alert mode")
    history_period=five_year_history_summary() if mode=="history5y" else None
    if mode=="history5y" and not history_period:
        return "skipped"
    required=("KAKAO_REST_API_KEY","KAKAO_CLIENT_SECRET","R2_ACCOUNT_ID",
              "R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY","R2_BUCKET_NAME")
    absent=[key for key in required if not os.getenv(key)]
    if absent:
        print("KAKAO_SKIP: integration not configured ("+",".join(absent)+")")
        return "skipped"

    progress=None
    issue=None
    if mode=="complete":
        if not PROGRESS.exists():
            print("KAKAO_SKIP: no backfill progress report")
            return "skipped"
        progress=json.loads(PROGRESS.read_text(encoding="utf-8"))
        if not progress.get("completed") or progress.get("verified_manifest_scopes")!=11000:
            print("KAKAO_SKIP: 11000 scopes not complete")
            return "skipped"
        if not os.getenv("GH_TOKEN"):
            raise NotificationError("GitHub issue token not configured")
        issue=find_completion_issue()
        if has_sent_comment(issue):
            print("KAKAO_SKIP: one-time completion message already sent")
            return "already_sent"

    from cryptography.fernet import Fernet
    client=storage or r2_client()
    if mode=="history5y":
        from botocore.exceptions import ClientError
        try:
            client.head_object(Bucket=os.environ["R2_BUCKET_NAME"],Key=HISTORY_SENT_OBJECT)
            print("KAKAO_SKIP: five-year completion message already sent")
            return "already_sent"
        except ClientError as error:
            code=str(error.response.get("Error",{}).get("Code",""))
            status=error.response.get("ResponseMetadata",{}).get("HTTPStatusCode")
            if code not in ("NoSuchKey","404","NotFound") and status!=404:
                raise NotificationError("Unable to verify prior five-year Kakao notification") from None
    cipher=token_cipher_secret()
    refresh_token=refresh if refresh is not None else get_refresh_token(client,cipher)
    if not refresh_token:
        print("KAKAO_SKIP: no initial refresh token")
        return "skipped"
    access, rotated=renew_access_token(refresh_token)
    if rotated and rotated!=refresh_token:
        save_refresh_token(client,cipher,rotated)
        print("KAKAO_TOKEN_REFRESH: rotated token securely persisted to private R2")
    else:
        print("KAKAO_TOKEN_REFRESH: access token refreshed")

    if mode=="refresh":
        return "refreshed"
    if mode=="test":
        text="[테스트] 서울 아파트 수집 알림 연결 확인\\n이 메시지는 실제 수집 완료 알림이 아닙니다."
    elif mode=="history5y":
        start_month,end_month=history_period
        text=f"[부동산 실거래 5년 누적 완료]\\n기간 {start_month[:4]}.{start_month[4:]}~{end_month[:4]}.{end_month[4:]} · 서울·경기·대전 61개 지역\\n매매·전월세 기록을 사이트에서 확인할 수 있습니다."
    else:
        text="[서울 아파트 과거자료 수집 완료]\\n매매 6,250개 / 전월세 4,750개\\n총 11,000개 지역·계약월 R2 저장 확인\\nGitHub에서 검증결과 확인"
    send(access,text)
    if mode=="history5y":
        client.put_object(Bucket=os.environ["R2_BUCKET_NAME"],Key=HISTORY_SENT_OBJECT,
                          Body=b"sent",ContentType="text/plain",ServerSideEncryption="AES256")
        print("KAKAO_COMPLETE: five-year message sent and idempotency marker saved")
    if issue is not None:
        record_sent_comment(issue)
        print("KAKAO_COMPLETE: one-time message sent and GitHub issue marked")
    else:
        print("KAKAO_TEST: message accepted by Kakao API")
    return "sent"


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=("test","complete","refresh","history5y"),required=True)
    args=parser.parse_args()
    try:
        notify(args.mode)
        return 0
    except (NotificationError, ValueError, KeyError) as exc:
        # Exceptions are sanitized: do not log the Kakao refresh or access tokens.
        print("KAKAO_ERROR:",str(exc),file=sys.stderr)
        return 1
    except Exception as exc:
        print("KAKAO_ERROR:",type(exc).__name__,file=sys.stderr)
        return 1


if __name__=="__main__":raise SystemExit(main())
