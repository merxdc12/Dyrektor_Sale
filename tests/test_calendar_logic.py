"""Calendar filtering and readiness checks independent of Qt."""
from datetime import datetime

from pinterest_os.calendar_logic import filter_entries, is_overdue, publication_checklist


def test_overdue_and_status_filter():
    now = datetime(2026, 11, 9, 12, 0)
    entries = [
        {"scheduled_at": "2026-11-09T11:59", "status": "PLANNED"},
        {"scheduled_at": "2026-11-09T12:01", "status": "READY"},
        {"scheduled_at": "2026-11-08T09:00", "status": "PUBLISHED"},
        {"scheduled_at": "2026-11-08T09:00", "status": "CANCELLED"},
    ]
    assert is_overdue(entries[0], now)
    assert not is_overdue(entries[2], now)
    assert len(filter_entries(entries, "ALL", True, now)) == 1
    assert len(filter_entries(entries, "READY", False, now)) == 1


def test_publishing_checklist(tmp_path):
    pin = {"title": "IoT tutorial", "description": "ESP32 guide",
           "destination_url": "https://example.com", "board_id": 3}
    png = tmp_path / "pin.png"
    png.write_bytes(b"PNG fixture")
    assert publication_checklist(pin, {"png_path": str(png)}) == []
    assert publication_checklist(pin, {"png_path": str(tmp_path / "missing.png")}) == [
        "PNG file does not exist at saved path"]
    assert publication_checklist(pin, None) == ["Exported PNG asset"]
    assert "Assigned board" in publication_checklist({**pin, "board_id": None}, None)
