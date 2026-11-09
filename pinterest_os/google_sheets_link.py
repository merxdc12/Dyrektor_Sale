"""Strict Google Sheets URL parsing and public CSV preview (no OAuth)."""
from __future__ import annotations

import csv
import io
import re
from urllib.parse import urlsplit, parse_qs
from urllib.request import Request, urlopen

_ID = re.compile(r"^[A-Za-z0-9_-]{20,200}$")
_MAX_BYTES = 2_000_000


def parse_sheet_url(value: str) -> tuple[str, str]:
    """Return (spreadsheet_id, gid). Reject redirects and non-Google hosts."""
    url = urlsplit(value.strip())
    if url.scheme != "https" or url.hostname != "docs.google.com" or url.username or url.password or url.port:
        raise ValueError("Use a Google Sheets URL on https://docs.google.com/")
    match = re.fullmatch(r"/spreadsheets/d/([A-Za-z0-9_-]+)/?(?:edit|view)?/?", url.path)
    if not match or not _ID.fullmatch(match.group(1)):
        raise ValueError("Invalid Google spreadsheet link")
    fragment = parse_qs(url.fragment)
    query = parse_qs(url.query)
    gid = (fragment.get("gid") or query.get("gid") or ["0"])[0]
    if not gid.isdecimal() or len(gid) > 15:
        raise ValueError("Invalid sheet gid")
    return match.group(1), gid


def public_csv_url(value: str) -> str:
    spreadsheet_id, gid = parse_sheet_url(value)
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"


def preview_public_sheet(value: str, *, max_rows: int = 10) -> list[list[str]]:
    """Read only a small public CSV export. Never send user credentials."""
    from urllib.request import build_opener, HTTPRedirectHandler

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            parsed = urlsplit(newurl)
            host = parsed.hostname or ""
            allowed = (host == "docs.google.com" or host == "googleusercontent.com"
                       or host.endswith(".googleusercontent.com"))
            if parsed.scheme != "https" or not allowed or parsed.username or parsed.password:
                raise ValueError("Redirect to untrusted or sign-in host blocked")
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    request = Request(public_csv_url(value), headers={"User-Agent": "ITHutir-PinterestOS/1.0"})
    opener = build_opener(NoRedirect())
    with opener.open(request, timeout=12) as response:
        content_type = response.headers.get("Content-Type", "").lower()
        if "text/csv" not in content_type and "application/octet-stream" not in content_type:
            raise ValueError("Google did not return CSV; sheet may be private")
        data = response.read(_MAX_BYTES + 1)
    if len(data) > _MAX_BYTES:
        raise ValueError("CSV exceeds 2 MB preview limit")
    rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))
    return rows[:max_rows]
