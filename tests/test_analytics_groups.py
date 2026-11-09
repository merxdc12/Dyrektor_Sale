"""Board/category aggregation uses imported evidence and current assignments."""
import pytest

from pinterest_os.analytics_metrics import group_performance
from pinterest_os.storage import Storage


def test_group_totals_and_unassigned(tmp_path):
    db = Storage(tmp_path / "groups.sqlite3")
    try:
        a = db.create("boards", name="Electronics", category="Other")
        b = db.create("boards", name="Homelab", category="Other")
        first = db.create("pins", title="First", board_id=a)
        second = db.create("pins", title="Second", board_id=b)
        third = db.create("pins", title="Unassigned")
        with db.conn:
            db.conn.executemany(
                "INSERT INTO pinterest_metrics(date,pin_id,impressions,outbound_clicks,saves) VALUES(?,?,?,?,?)",
                [("2026-11-01", first, 100, 5, 2),
                 ("2026-11-02", first, 100, 15, 3),
                 ("2026-11-01", second, 50, 2, 1),
                 ("2026-11-01", third, 20, 1, 0)])
        boards = group_performance(db)
        assert len(boards) == 3
        assert boards[0]["name"] == "Electronics"
        assert boards[0]["pins"] == 1
        assert boards[0]["impressions"] == 200
        assert boards[0]["outbound_clicks"] == 20
        assert boards[0]["ctr"] == 10.0
        assert any(row["name"] == "Unassigned" for row in boards)
        categories = group_performance(db, "category")
        other = next(row for row in categories if row["name"] == "Other")
        assert other["pins"] == 2
        assert other["impressions"] == 250
        assert other["outbound_clicks"] == 22
        assert other["ctr"] == 8.8
        with pytest.raises(ValueError, match="Unsupported"):
            group_performance(db, "invalid")
    finally:
        db.close()
