"""Offline manual publishing workflow; never sends data to Pinterest."""
from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

from .calendar_logic import publication_checklist


def validate_destination(url: str) -> bool:
    parsed = urlparse(url.strip())
    return parsed.scheme in ("https", "http") and bool(parsed.hostname)


def publishing_issues(pin: dict, design: dict | None) -> list[str]:
    issues = publication_checklist(pin, design)
    if pin.get("destination_url", "").strip() and not validate_destination(pin["destination_url"]):
        issues.append("Destination URL must be HTTP(S) with a hostname")
    return issues


def pending_queue(storage, now: datetime | None = None) -> list[dict]:
    """Return local schedule entries eligible for manual review, oldest first."""
    today = (now or datetime.now()).strftime("%Y-%m-%d")
    rows = storage.schedules_between("2000-01-01", today)
    return [row for row in rows if row["status"] in ("PLANNED", "READY")
            and (storage.get("pins", row["pin_id"]) or {}).get("status") != "PUBLISHED"]


def mark_published(storage, entry_id: int) -> None:
    """User-confirmed local record update, not a Pinterest verification."""
    entry = storage.get_schedule(entry_id)
    if not entry:
        raise ValueError("Calendar entry no longer exists")
    pin = storage.get("pins", entry["pin_id"])
    if not pin:
        raise ValueError("Pin no longer exists")
    if pin["status"] == "PUBLISHED":
        raise ValueError("Pin already marked as published")
    if entry["status"] == "CANCELLED":
        raise ValueError("Cancelled calendar entry cannot be published")
    if entry["status"] == "PUBLISHED":
        raise ValueError("Already marked as published")
    issues = publishing_issues(pin, storage.get_pin_design(pin["id"]))
    if issues:
        raise ValueError("Incomplete publishing checklist: " + ", ".join(issues))
    storage.confirm_manual_publication(entry_id)
