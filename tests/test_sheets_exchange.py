"""Offline Google Sheets exchange validation and SQLite roundtrip."""
import pytest
from pinterest_os.storage import Storage
from pinterest_os.sheets_exchange import (
    parse_pin_rows, import_pin_rows, export_pin_rows, export_time_rows,
    export_metric_rows, PIN_FIELDS, TIME_FIELDS, METRIC_FIELDS,
)


def test_pin_exchange_and_rejection(tmp_path):
    db = Storage(tmp_path / "exchange.sqlite3")
    try:
        db.create("boards", name="Makers")
        db.create("products", name="Kit", category="POD")
        rows = [list(PIN_FIELDS), ["Pin A", "Description", "https://example.org",
                                 "DRAFT", "Makers", "Kit"]]
        records = parse_pin_rows(rows, db)
        assert len(records) == 1
        assert import_pin_rows(db, records) == 1
        exported = export_pin_rows(db)
        assert exported[0]["board"] == "Makers"
        assert exported[0]["product"] == "Kit"
        assert set(exported[0]) == set(PIN_FIELDS)
        with pytest.raises(ValueError, match="unknown board"):
            parse_pin_rows([list(PIN_FIELDS),
                            ["Bad", "", "", "DRAFT", "Unknown", ""]], db)
        assert len(db.all("pins")) == 1
        assert export_time_rows(db) == []
        assert export_metric_rows(db) == []
        assert len(TIME_FIELDS) == 9
        assert len(METRIC_FIELDS) == 5
    finally:
        db.close()
