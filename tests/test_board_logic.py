"""Board management regression checks without Qt or network access."""
from datetime import date
from pathlib import Path

from pinterest_os.board_logic import CATEGORIES, board_plan, board_seo_issues
from pinterest_os.storage import Storage


def test_board_categories_and_assignment(tmp_path: Path):
    storage = Storage(tmp_path / "board.sqlite3")
    try:
        board = storage.create("boards", name="Embedded & IoT", description="Practical tutorials for ESP32 makers.",
                               category=CATEGORIES[1])
        pin = storage.create("pins", title="ESP32 setup", board_id=board, status="READY")
        assert storage.board_pin_count(board) == 1
        assert storage.board_pin_counts()[board] == 1
        assert storage.search_boards("esp32") == []
        assert len(storage.search_boards("embedded")) == 1
        assert storage.get("boards", board)["category"] == CATEGORIES[1]
        assert board_plan(storage.get("boards", board), storage.all("pins"),
                          date(2026, 11, 9))[0]["date"] == "2026-11-09"
        assert storage.delete_board(board)
        assert storage.get("pins", pin)["board_id"] is None
    finally:
        storage.close()


def test_board_seo_advice_and_plan_order():
    assert not board_seo_issues(
        "Linux and Homelab", "Guides for self-hosting and Linux home servers, networking and backups.",
        "https://www.pinterest.com/example/linux/")
    assert board_seo_issues("IoT", "", "http://other.example/board")
    board = {"id": 7}
    pins = [
        {"id": 2, "board_id": 7, "title": "Draft", "status": "DRAFT"},
        {"id": 1, "board_id": 7, "title": "Ready", "status": "READY"},
        {"id": 3, "board_id": 8, "title": "Other", "status": "READY"},
        {"id": 4, "board_id": 7, "title": "Published", "status": "PUBLISHED"},
    ]
    planned = board_plan(board, pins, date(2026, 11, 9))
    assert [p["pin_id"] for p in planned] == [1, 2]
