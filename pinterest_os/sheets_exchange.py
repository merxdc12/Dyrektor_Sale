"""Validated, append-only local pin imports and read-only export snapshots."""
from __future__ import annotations
from .csv_io import FIELDS as PIN_FIELDS
from .storage import utc_now

TIME_FIELDS = ("entry_id","session_id","task","pin_id","product_id_snapshot",
               "product_name_snapshot","attribution_known","seconds","created_at")
METRIC_FIELDS = ("date","pin_id","impressions","outbound_clicks","saves")


def parse_pin_rows(rows, storage):
    if not rows or list(rows[0]) != list(PIN_FIELDS):
        raise ValueError("Expected pin columns: " + ", ".join(PIN_FIELDS))
    if len(rows) > 10001:
        raise ValueError("Too many pin rows (max 10000)")
    boards = {row["name"]: row["id"] for row in storage.all("boards")}
    products = {row["name"]: row["id"] for row in storage.all("products")}
    result = []
    for index, values in enumerate(rows[1:], 2):
        if len(values) > len(PIN_FIELDS):
            raise ValueError(f"Row {index}: too many cells")
        record = dict(zip(PIN_FIELDS, list(values) + [""] * (len(PIN_FIELDS) - len(values))))
        title = record["title"].strip()
        status = record["status"].strip() or "DRAFT"
        board = record["board"].strip()
        product = record["product"].strip()
        if not title or len(title) > 300:
            raise ValueError(f"Row {index}: title required (max 300 chars)")
        if status not in {"DRAFT", "IN_REVIEW", "READY", "PUBLISHED"}:
            raise ValueError(f"Row {index}: invalid status")
        if board and board not in boards:
            raise ValueError(f"Row {index}: unknown board '{board}'")
        if product and product not in products:
            raise ValueError(f"Row {index}: unknown product '{product}'")
        if len(record["description"]) > 5000 or len(record["destination_url"]) > 4096:
            raise ValueError(f"Row {index}: text too long")
        result.append((title, record["description"], record["destination_url"],
                       status, boards.get(board), products.get(product), utc_now()))
    return result


def import_pin_rows(storage, records):
    with storage.conn:
        storage.conn.executemany(
            """INSERT INTO pins(title,description,destination_url,status,board_id,product_id,created_at)
               VALUES(?,?,?,?,?,?,?)""", records)
    return len(records)


def export_pin_rows(storage):
    boards = {r["id"]: r["name"] for r in storage.all("boards")}
    products = {r["id"]: r["name"] for r in storage.all("products")}
    return [{**{key: pin.get(key) or "" for key in PIN_FIELDS[:4]},
             "board": boards.get(pin.get("board_id"), ""),
             "product": products.get(pin.get("product_id"), "")}
            for pin in storage.all("pins")]


def export_time_rows(storage):
    query = """SELECT id,session_id,task,pin_id,product_id_snapshot,
                      product_name_snapshot,attribution_known,seconds,created_at
               FROM time_entries ORDER BY id"""
    return [dict(zip(TIME_FIELDS, ("" if v is None else v for v in row)))
            for row in storage.conn.execute(query)]


def export_metric_rows(storage):
    return [dict(zip(METRIC_FIELDS, row)) for row in storage.conn.execute(
        """SELECT date,pin_id,impressions,outbound_clicks,saves
           FROM pinterest_metrics ORDER BY date,pin_id""")]
