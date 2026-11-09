"""Portable product metadata CSV/JSON exchange (no remote API).

Imports are validated in full before any database writes. IDs are not imported:
new local IDs are assigned, preventing accidental modification of existing pins.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

COLUMNS = ("name", "category", "target_url")
CATEGORIES = frozenset({"POD", "KDP", "DIGITAL", "FREE_TOOL", "OTHER"})


def validate_products(records: list[dict]) -> list[dict]:
    if not isinstance(records, list):
        raise ValueError("Expected a list of products")
    result = []
    for index, row in enumerate(records, 1):
        if not isinstance(row, dict):
            raise ValueError(f"Row {index} is not an object")
        if set(row) - set(COLUMNS):
            raise ValueError(f"Row {index}: unexpected fields")
        name = row.get("name", "")
        category = row.get("category", "POD")
        url = row.get("target_url", "")
        if not all(isinstance(x, str) for x in (name, category, url)):
            raise ValueError(f"Row {index}: fields must be strings")
        name, category, url = name.strip(), category.strip(), url.strip()
        if not name:
            raise ValueError(f"Row {index}: product name is required")
        if category not in CATEGORIES:
            raise ValueError(f"Row {index}: unsupported category {category!r}")
        if len(name) > 300 or len(url) > 4096:
            raise ValueError(f"Row {index}: field too long")
        result.append({"name": name, "category": category, "target_url": url})
    return result


def read_products(path: str | Path) -> list[dict]:
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames is None or set(reader.fieldnames) != set(COLUMNS):
                raise ValueError("CSV must have name, category, target_url headers")
            rows = list(reader)
    elif path.suffix.lower() == ".json":
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict) or data.get("format") != "ithutir-products-v1":
            raise ValueError("Unsupported products JSON format")
        rows = data.get("products")
    else:
        raise ValueError("Only .csv and .json files are supported")
    return validate_products(rows)


def import_products(storage, path: str | Path) -> int:
    rows = read_products(path)
    # Explicit transaction prevents partial imports.
    with storage.conn:
        for row in rows:
            storage.conn.execute(
                "INSERT INTO products(name,category,target_url,created_at) VALUES(?,?,?,?)",
                (row["name"], row["category"], row["target_url"], __utc_now()),
            )
    return len(rows)


def __utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def export_products(storage, path: str | Path) -> int:
    destination = Path(path)
    rows = validate_products([
        {key: row[key] for key in COLUMNS} for row in storage.all("products")
    ])
    if destination.suffix.lower() == ".csv":
        with destination.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
    elif destination.suffix.lower() == ".json":
        with destination.open("w", encoding="utf-8") as file:
            json.dump({"format": "ithutir-products-v1", "products": rows},
                      file, ensure_ascii=False, indent=2)
    else:
        raise ValueError("Only .csv and .json files are supported")
    return len(rows)
