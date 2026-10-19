#!/usr/bin/env python3
# coding: utf-8
"""One-time Google Drive OAuth setup on USER PC. No credentials written to disk.

Requires locally downloaded OAuth client of type Desktop:
C:\EdwardTools\GoogleDriveBackup\google_oauth_client.json
Never upload the JSON or refresh token to a public repository or this chat.
"""
import json
import os
import sys
from pathlib import Path


def main():
    import argparse
    from google_auth_oauthlib.flow import InstalledAppFlow
    parser=argparse.ArgumentParser()
    parser.add_argument("--client-json",default=str(Path(__file__).with_name("google_oauth_client.json")))
    args=parser.parse_args()
    path=Path(args.client_json)
    if not path.is_file():
        print("ERROR: save the downloaded Desktop OAuth JSON as google_oauth_client.json next to this script.")
        return 1
    try:
        data=json.loads(path.read_text(encoding="utf-8-sig"))
        client=data["installed"]
        if not client.get("client_id") or not client.get("client_secret"):
            raise ValueError("Client ID/Secret missing")
    except (KeyError,ValueError,OSError):
        print("ERROR: Desktop OAuth client JSON is invalid. Web application credentials are not supported.")
        return 1
    print("Use the SAME Google account that owns your 5TB Drive storage.")
    print("Only permission requested: create/manage this application's own Drive files (drive.file).")
    print("Consent-screen external Testing mode can expire refresh tokens after 7 days.")
    try:
        flow=InstalledAppFlow.from_client_secrets_file(str(path),
                   scopes=["https://www.googleapis.com/auth/drive.file"],autogenerate_code_verifier=True)
        creds=flow.run_local_server(
            host="127.0.0.1",port=0,open_browser=True,
            authorization_prompt_message="Open this login URL in a local browser if it does not open automatically: {url}",
            success_message="Google OAuth approval received. Close this tab and return to the terminal.",
            access_type="offline",prompt="consent",
        )
    except Exception:
        print("ERROR: OAuth failed. Check Google Auth Platform Audience, Test Users, desktop app and browser.")
        return 1
    if not creds.refresh_token:
        print("ERROR: Google did not issue an offline refresh token; revoke previous app access and retry.")
        return 1
    print("\nSUCCESS. Copy ONLY the following values to GitHub repository Secrets.")
    print("GOOGLE_OAUTH_CLIENT_ID="+client["client_id"])
    print("GOOGLE_OAUTH_CLIENT_SECRET="+client["client_secret"])
    print("GOOGLE_OAUTH_REFRESH_TOKEN="+creds.refresh_token)
    print("\nKeep this terminal private. Do not share a screenshot of these values.")
    print("No token files were created by this program; remove google_oauth_client.json securely once Secrets are saved.")
    return 0


if __name__=="__main__":raise SystemExit(main())
