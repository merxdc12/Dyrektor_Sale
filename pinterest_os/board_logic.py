"""Offline board SEO guidance and editorial planning; no Pinterest API claims."""
from __future__ import annotations

from datetime import date, timedelta
from urllib.parse import urlparse

CATEGORIES = ("Linux & Homelab", "Embedded & IoT", "Electronics Tutorials",
              "IT Word Search & Books", "POD Tech Merch", "DIY Smart Home",
              "Software & DevOps", "Other")


def board_seo_issues(name: str, description: str, url: str = "") -> list[str]:
    """Editorial checks, not official Pinterest ranking requirements."""
    issues = []
    name, description, url = name.strip(), description.strip(), url.strip()
    if not name:
        issues.append("Board name is required.")
    elif len(name) > 50:
        issues.append("Name exceeds 50 characters (editorial recommendation).")
    if not description:
        issues.append("Add a descriptive, natural-language SEO description.")
    elif len(description) < 40:
        issues.append("Description is short; explain the audience and subject.")
    elif len(description) > 500:
        issues.append("Description exceeds 500 characters (editorial recommendation).")
    if url:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in ("pinterest.com", "www.pinterest.com"):
            issues.append("Board URL must be an HTTPS pinterest.com link.")
    return issues


def board_plan(board: dict, pins: list[dict], start: date | None = None, days: int = 14) -> list[dict]:
    """Suggest dates for unposted pins; never schedules or publishes automatically."""
    if days < 1 or days > 90:
        raise ValueError("Planning horizon must be 1–90 days")
    start = start or date.today()
    candidates = [p for p in pins if p.get("board_id") == board["id"]
                  and p.get("status") != "PUBLISHED"]
    candidates.sort(key=lambda p: (p.get("status") != "READY", p["id"]))
    return [{"date": (start + timedelta(days=i)).isoformat(),
             "pin_id": pin["id"], "title": pin["title"], "status": pin["status"]}
            for i, pin in enumerate(candidates[:days])]
