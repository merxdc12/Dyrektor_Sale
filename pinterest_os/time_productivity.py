"""TIME 4: descriptive work-efficiency indicators, not profitability claims."""
from decimal import Decimal, ROUND_HALF_UP
from .time_page import product_time_summary


def productivity_rows(storage, currency=None):
    """Per-product logged seconds / distinct worked-on pins.

    A pin is counted only when it has time entries. Legacy attribution is
    unknown, and unassigned time is never allocated to a product.
    """
    base = product_time_summary(storage, currency)
    pin_rows = storage.conn.execute(
        """SELECT attribution_known, product_id_snapshot, product_name_snapshot,
                  pin_id, SUM(seconds)
           FROM time_entries
           WHERE pin_id IS NOT NULL
           GROUP BY attribution_known, product_id_snapshot, product_name_snapshot, pin_id"""
    ).fetchall()
    counts = {}
    for known, product_id, name, pin_id, seconds in pin_rows:
        key = (known, product_id, name)
        counts.setdefault(key, set()).add(pin_id)
    result = []
    for row in base:
        known = row["attribution_known"]
        product_id = row["product_id"]
        name = row["product_name"]
        # Legacy name is normalized for display; it must not be treated as a
        # reliable historical product identity.
        if known:
            count = len(counts.get((1, product_id, None if product_id is None else name), set()))
        else:
            count = len(set().union(*(pins for (flag, _, _), pins in counts.items()
                                     if not flag))) if counts else 0
        seconds_per_pin = (Decimal(row["seconds"]) / Decimal(count)
                           if count else None)
        labor_per_pin = (Decimal(row["labor_cents"]) / Decimal(count)
                         if count and row["labor_cents"] is not None else None)
        result.append({**row, "worked_pins": count,
                       "seconds_per_worked_pin": seconds_per_pin,
                       "labor_cents_per_worked_pin": labor_per_pin})
    return result
