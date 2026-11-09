"""Pure offline calendar filtering and publishing-readiness helpers."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

STATUSES = ("PLANNED", "READY", "PUBLISHED", "CANCELLED")


def is_overdue(entry: dict, now: datetime) -> bool:
    """Overdue means an uncompleted scheduled action is earlier than local now."""
    if entry["status"] in ("PUBLISHED", "CANCELLED"):
        return False
    return datetime.strptime(entry["scheduled_at"], "%Y-%m-%dT%H:%M") < now


def filter_entries(entries: list[dict], status: str = "ALL",
                   overdue_only: bool = False, now: datetime | None = None) -> list[dict]:
    if status not in ("ALL", *STATUSES):
        raise ValueError("Invalid calendar status filter")
    now = now or datetime.now()
    return [row for row in entries
            if (status == "ALL" or row["status"] == status)
            and (not overdue_only or is_overdue(row, now))]


def publication_checklist(pin: dict, design: dict | None) -> list[str]:
    """Editorial checklist only; cannot verify remote Pinterest publication."""
    missing = []
    if not pin.get("title", "").strip():
        missing.append("Pin title")
    if not pin.get("description", "").strip():
        missing.append("Pin description")
    if not pin.get("destination_url", "").strip():
        missing.append("Destination URL")
    if pin.get("board_id") is None:
        missing.append("Assigned board")
    png = (design or {}).get("png_path") or ""
    if not png.strip():
        missing.append("Exported PNG asset")
    elif not Path(png).is_file():
        missing.append("PNG file does not exist at saved path")
    return missing
