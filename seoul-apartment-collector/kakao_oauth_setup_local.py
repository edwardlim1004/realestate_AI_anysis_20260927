#!/usr/bin/env python3
# coding: utf-8
"""One-time local OAuth setup for Kakao My Chat, with no token written to disk.

Register redirect URL http://127.0.0.1:8769/callback in Kakao Developers.
The refresh token will be shown once in the terminal; paste only in GitHub Secret.
"""
import getpass
import http.server
import json
import secrets
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser

CALLBACK="http://127.0.0.1:8769/callback"
AUTH="https://kauth.kakao.com/oauth/authorize"
TOKEN="https://kauth.kakao.com/oauth/token"


def main():
    print("카카오 Developers에서 로그인 ON, talk_message 동의항목, Redirect URI 등록을 먼저 진행하세요.")
    print("Redirect URI:",CALLBACK)
    api_key=input("Kakao REST API 키: ").strip()
    client_secret=getpass.getpass("Kakao REST API Client Secret (입력 숨김): ").strip()
    if not api_key or not client_secret:
        print("REST API Key와 Client Secret이 모두 필요합니다.")
        return 1
    state=secrets.token_urlsafe(24)
    answer={}
    signal=threading.Event()
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            parts=urllib.parse.urlsplit(self.path)
            data=urllib.parse.parse_qs(parts.query)
            if parts.path!="/callback":
                self.send_error(404);return
            if data.get("state",[None])[0]!=state:
                self.send_error(403);return
            answer["code"]=data.get("code",[None])[0]
            answer["error"]=data.get("error",[None])[0]
            self.send_response(200)
            self.send_header("Content-Type","text/html;charset=utf-8")
            self.end_headers()
            self.wfile.write("<html><body>카카오 인증을 받았습니다. 이 브라우저를 닫고 명령창을 확인하세요.</body></html>".encode("utf-8"))
            signal.set()
    try:
        server=http.server.HTTPServer(("127.0.0.1",8769),Handler)
    except OSError:
        print("로컬 8769 포트 사용 중입니다. 해당 프로그램을 종료하고 다시 실행하세요.")
        return 1
    url=AUTH+"?"+urllib.parse.urlencode({
        "client_id":api_key,"redirect_uri":CALLBACK,"response_type":"code",
        "scope":"talk_message","state":state})
    print("\n이제 Kakao 계정으로 로그인하고 '카카오톡 메시지 전송'에 동의하세요.")
    print("브라우저가 열리지 않으면 아래 URL을 직접 열 수 있습니다 (외부 공유 금지):")
    print(url)
    webbrowser.open(url)
    with server:
        server.timeout=5
        for _ in range(36):
            if signal.is_set():break
            server.handle_request()
        if not signal.is_set():
            print("인증 시간 초과 (3분). 다시 시도하세요.")
            return 1
    if not answer.get("code"):
        print("로그인이 취소되었거나 권한에 동의하지 않았습니다.",answer.get("error"))
        return 1
    data=urllib.parse.urlencode({
        "grant_type":"authorization_code","client_id":api_key,
        "client_secret":client_secret,"redirect_uri":CALLBACK,
        "code":answer["code"]}).encode("utf-8")
    try:
        req=urllib.request.Request(TOKEN,data=data,headers={
            "Content-Type":"application/x-www-form-urlencoded;charset=utf-8"})
        with urllib.request.urlopen(req,timeout=20) as resp:
            payload=json.load(resp)
    except Exception:
        print("카카오 토큰 발급 실패. 앱 설정과 Redirect URI, Client Secret을 확인하세요.")
        return 1
    refresh=payload.get("refresh_token")
    if not isinstance(refresh,str) or not refresh:
        print("카카오 서버에서 갱신 토큰을 받지 못했습니다.")
        return 1
    print("\n인증에 성공했습니다.")
    print("GitHub Secret Name: KAKAO_REFRESH_TOKEN")
    print("GitHub Secret Value: "+refresh)
    print("\n이 값은 절대 GitHub 코드나 채팅에 붙이지 마세요. GitHub Secrets에만 입력하세요.")
    print("액세스 토큰은 표시하지 않습니다. 토큰을 GitHub에 등록했다면 이 창을 닫으세요.")
    return 0


if __name__=="__main__":sys.exit(main())
