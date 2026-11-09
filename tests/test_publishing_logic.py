"""Publishing is manual and local-only."""
from pathlib import Path

import pytest

from pinterest_os.publishing_logic import (
    mark_published, pending_queue, publishing_issues, validate_destination,
)
from pinterest_os.storage import Storage


def test_url_validation():
    assert validate_destination("https://example.com/product")
    assert not validate_destination("javascript:alert(1)")
    assert not validate_destination("example.com")


def test_manual_confirmation_requires_complete_pin(tmp_path: Path):
    storage = Storage(tmp_path / "publish.sqlite3")
    try:
        board = storage.create("boards", name="Electronics")
        pin = storage.create("pins", title="Ohm calculator", description="Calculate Ohm's law",
                             destination_url="https://example.com", board_id=board)
        entry = storage.create_schedule(pin, "2026-01-01T10:00", "READY")
        assert len(pending_queue(storage)) == 1
        with pytest.raises(ValueError, match="checklist"):
            mark_published(storage, entry)
        png = tmp_path / "pin.png"
        png.write_bytes(b"fixture")
        storage.save_pin_design(pin, '{"version":1}', str(png))
        assert publishing_issues(storage.get("pins", pin), storage.get_pin_design(pin)) == []
        mark_published(storage, entry)
        assert storage.get_schedule(entry)["status"] == "PUBLISHED"
        assert storage.get("pins", pin)["status"] == "PUBLISHED"
        assert pending_queue(storage) == []
        with pytest.raises(ValueError, match="Already"):
            mark_published(storage, entry)
    finally:
        storage.close()


def test_duplicate_schedules_and_repeat_confirmation(tmp_path: Path):
    storage = Storage(tmp_path / "duplicates.sqlite3")
    try:
        board = storage.create("boards", name="IoT")
        pin = storage.create("pins", title="Guide", description="How to use ESP32",
                             destination_url="https://example.com/guide", board_id=board)
        first = storage.create_schedule(pin, "2026-01-01T09:00", "READY")
        second = storage.create_schedule(pin, "2026-01-01T10:00", "PLANNED")
        image = tmp_path / "pin.png"
        image.write_bytes(b"fixture")
        storage.save_pin_design(pin, '{"version":1}', str(image))
        assert len(pending_queue(storage)) == 2
        mark_published(storage, first)
        assert storage.get_schedule(first)["status"] == "PUBLISHED"
        assert storage.get_schedule(second)["status"] == "CANCELLED"
        assert pending_queue(storage) == []
        with pytest.raises(ValueError, match="already"):
            mark_published(storage, second)
        with pytest.raises(ValueError, match="already"):
            mark_published(storage, first)
    finally:
        storage.close()


def test_queue_date_boundary_and_order(tmp_path: Path):
    from datetime import datetime
    storage = Storage(tmp_path / "queue.sqlite3")
    try:
        pin = storage.create("pins", title="First")
        old = storage.create_schedule(pin, "2026-01-01T08:00")
        today = storage.create_schedule(pin, "2026-01-02T18:00")
        storage.create_schedule(pin, "2026-01-03T08:00")
        queue = pending_queue(storage, datetime(2026, 1, 2, 9, 0))
        assert [row["id"] for row in queue] == [old, today]
    finally:
        storage.close()
