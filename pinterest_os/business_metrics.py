"""Explicitly attributed business metrics. Never infer sales from Pinterest clicks.

Normalized CSV: date,pin_id,currency,site_visits,conversions,revenue,cost
Revenue/cost are decimal currency amounts; stored as integer minor units.
Cost is reported/allocated cost only, not guaranteed full business cost.
"""
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

COLUMNS = ("date", "pin_id", "currency", "site_visits", "conversions", "revenue", "cost")


def minor_units(value):
    try:
        number = Decimal(value.strip())
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError("invalid monetary amount") from exc
    if not number.is_finite() or number < 0 or number.as_tuple().exponent < -2:
        raise ValueError("amount must be nonnegative with at most two decimals")
    return int(number * 100)


def parse_business_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not set(COLUMNS).issubset(reader.fieldnames):
            raise ValueError("CSV must contain: " + ", ".join(COLUMNS))
        rows, seen = [], set()
        for line, raw in enumerate(reader, 2):
            try:
                day = date.fromisoformat(raw["date"].strip()).isoformat()
                pin_id = int(raw["pin_id"])
                currency = raw["currency"].strip().upper()
                visits = int(raw["site_visits"])
                conversions = int(raw["conversions"])
                revenue = minor_units(raw["revenue"])
                cost = minor_units(raw["cost"])
                if (pin_id <= 0 or len(currency) != 3 or not currency.isascii()
                        or not currency.isalpha() or visits < 0 or conversions < 0):
                    raise ValueError("invalid value")
            except (ValueError, TypeError, AttributeError) as exc:
                raise ValueError(f"CSV line {line}: invalid value") from exc
            key = (day, pin_id, currency)
            if key in seen:
                raise ValueError(f"CSV line {line}: duplicate date/pin_id/currency")
            seen.add(key)
            rows.append((day, pin_id, currency, visits, conversions, revenue, cost))
    if not rows:
        raise ValueError("CSV has no data rows")
    return rows


def import_business_metrics(storage, path):
    rows = parse_business_csv(path)
    missing = sorted({row[1] for row in rows if not storage.get("pins", row[1])})
    if missing:
        raise ValueError("Unknown local pin IDs: " + ", ".join(map(str, missing)))
    with storage.conn:
        storage.conn.executemany(
            """INSERT INTO business_metrics
               (date,pin_id,currency,site_visits,conversions,revenue_cents,reported_cost_cents)
               VALUES(?,?,?,?,?,?,?)
               ON CONFLICT(date,pin_id,currency) DO UPDATE SET
               site_visits=excluded.site_visits,conversions=excluded.conversions,
               revenue_cents=excluded.revenue_cents,
               reported_cost_cents=excluded.reported_cost_cents""", rows)
    return len(rows)


def business_summary(storage, currency="USD"):
    rows = storage.conn.execute(
        """SELECT p.id,p.title,SUM(b.site_visits),SUM(b.conversions),
                  SUM(b.revenue_cents),SUM(b.reported_cost_cents)
           FROM business_metrics b JOIN pins p ON p.id=b.pin_id
           WHERE b.currency=? GROUP BY p.id,p.title
           ORDER BY SUM(b.revenue_cents)-SUM(b.reported_cost_cents) DESC,p.id""",
        (currency,),
    ).fetchall()
    return [
        {"pin_id": pid, "title": title, "visits": visits, "conversions": conversions,
         "revenue_cents": revenue, "reported_cost_cents": cost,
         "contribution_cents": revenue - cost,
         "conversion_rate": (100 * conversions / visits) if visits else None}
        for pid, title, visits, conversions, revenue, cost in rows
    ]
