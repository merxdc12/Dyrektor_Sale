"""Offline import of explicitly mapped Pinterest Analytics CSV exports.

Required normalized columns: date,pin_id,impressions,outbound_clicks,saves.
pin_id is the local ITHutir pin ID, not a Pinterest ID.
"""
import csv
from datetime import date
from pathlib import Path

FIELDS = ("date", "pin_id", "impressions", "outbound_clicks", "saves")


def parse_metrics_csv(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not set(FIELDS).issubset(reader.fieldnames):
            raise ValueError("CSV must contain: " + ", ".join(FIELDS))
        rows = []
        seen = set()
        for line, raw in enumerate(reader, 2):
            try:
                day = date.fromisoformat(raw["date"].strip()).isoformat()
                pin_id = int(raw["pin_id"])
                numbers = [int(raw[key]) for key in FIELDS[2:]]
                if pin_id <= 0 or any(number < 0 for number in numbers):
                    raise ValueError("negative metric or invalid pin ID")
            except (ValueError, TypeError, AttributeError) as exc:
                raise ValueError(f"CSV line {line}: invalid date, ID or metric") from exc
            key = (day, pin_id)
            if key in seen:
                raise ValueError(f"CSV line {line}: duplicate date/pin_id")
            seen.add(key)
            rows.append((day, pin_id, *numbers))
    if not rows:
        raise ValueError("CSV has no data rows")
    return rows


def import_metrics(storage, path):
    """Upsert a snapshot per local pin per day, atomically."""
    rows = parse_metrics_csv(path)
    missing = sorted({row[1] for row in rows if not storage.get("pins", row[1])})
    if missing:
        raise ValueError("Unknown local pin IDs: " + ", ".join(map(str, missing)))
    with storage.conn:
        storage.conn.executemany(
            """INSERT INTO pinterest_metrics
               (date,pin_id,impressions,outbound_clicks,saves)
               VALUES(?,?,?,?,?)
               ON CONFLICT(date,pin_id) DO UPDATE SET
               impressions=excluded.impressions,
               outbound_clicks=excluded.outbound_clicks,
               saves=excluded.saves""", rows)
    return len(rows)


def metric_history(storage):
    return storage.conn.execute(
        """SELECT date,SUM(impressions),SUM(outbound_clicks),SUM(saves)
           FROM pinterest_metrics GROUP BY date ORDER BY date"""
    ).fetchall()
