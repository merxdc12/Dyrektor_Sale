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
