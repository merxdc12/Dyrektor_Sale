"""Opt-in Google Sheets OAuth and safe, explicit worksheet exchange.

Credentials are stored in the operating-system keyring, not SQLite or QSettings.
Requires google-auth-oauthlib, google-api-python-client, keyring.
"""
from __future__ import annotations
import csv
import io
import json
import re

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SERVICE = "ITHutir-PinterestOS-GoogleSheets"
ACCOUNT = "oauth-credentials"
TAB = re.compile(r"^[^\\[\\]*?/\\?:]{1,100}$")


def _dependencies():
    try:
        import keyring
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Install optional Google integration: pip install -r requirements-google.txt"
        ) from exc
    return keyring, Credentials, InstalledAppFlow, Request, build


def _load():
    keyring, Credentials, _, Request, build = _dependencies()
    raw = keyring.get_password(SERVICE, ACCOUNT)
    if not raw:
        raise RuntimeError("Not connected. Select Connect Google first.")
    credentials = Credentials.from_authorized_user_info(json.loads(raw), SCOPES)
    if not credentials.valid:
        if not credentials.refresh_token:
            raise RuntimeError("Google authorization expired. Reconnect.")
        credentials.refresh(Request())
        keyring.set_password(SERVICE, ACCOUNT, credentials.to_json())
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def connect(client_secret_file: str):
    keyring, _, Flow, _, _ = _dependencies()
    flow = Flow.from_client_secrets_file(client_secret_file, SCOPES)
    credentials = flow.run_local_server(host="127.0.0.1", port=0, open_browser=True)
    keyring.set_password(SERVICE, ACCOUNT, credentials.to_json())
    return True


def disconnect():
    keyring, *_ = _dependencies()
    keyring.delete_password(SERVICE, ACCOUNT)


def worksheets(spreadsheet_id: str):
    service = _load()
    result = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id, fields="sheets(properties(sheetId,title))"
    ).execute()
    return [(s["properties"]["sheetId"], s["properties"]["title"])
            for s in result.get("sheets", [])]


def _range(title):
    if not title or len(title) > 100 or any(ch in title for ch in "[]:*?/\\"):
        raise ValueError("Invalid worksheet title")
    return "'" + title.replace("'", "''") + "'"


def read_rows(spreadsheet_id: str, title: str, limit=1000):
    service = _load()
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=f"{_range(title)}!A1:AZ{limit}",
        valueRenderOption="FORMATTED_VALUE"
    ).execute()
    return result.get("values", [])


def create_export_tab(spreadsheet_id: str, title: str, headers, records):
    """Create a NEW worksheet; never overwrite or modify existing user data."""
    if len(records) > 10000:
        raise ValueError("Export limited to 10,000 records")
    if not headers or len(headers) > 52:
        raise ValueError("Invalid export headers")
    service = _load()
    created = service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": title}}}]}
    ).execute()
    sheet_id = created["replies"][0]["addSheet"]["properties"]["sheetId"]
    rows = [list(headers)] + [
        [safe_cell(record.get(field, "")) for field in headers] for record in records
    ]
    try:
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{_range(title)}!A1",
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()
    except Exception:
        # A failed upload leaves the new tab in place for inspection/recovery.
        raise
    return sheet_id, len(records)


def safe_cell(value):
    if value is None:
        return ""
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text
