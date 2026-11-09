"""Cost ledger and labor valuation; estimates are NOT verified net profit."""
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from .storage import utc_now


def money_cents(value):
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Invalid amount") from exc
    if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2:
        raise ValueError("Amount must be nonnegative with at most two decimals")
    return int(amount * 100)


def valid_currency(currency):
    currency = currency.strip().upper()
    if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
        raise ValueError("Currency must be a three-letter code")
    return currency


def add_cost(storage, day, currency, category, description, amount, pin_id=None):
    date.fromisoformat(day)
    currency = valid_currency(currency)
    if category not in ("DIRECT", "ALLOCATED"):
        raise ValueError("Invalid cost category")
    if not description.strip():
        raise ValueError("Cost description required")
    if pin_id is not None and not storage.get("pins", pin_id):
        raise ValueError("Unknown pin ID")
    with storage.conn:
        cursor = storage.conn.execute(
            """INSERT INTO cost_entries
               (date,pin_id,currency,category,description,amount_cents,created_at)
               VALUES(?,?,?,?,?,?,?)""",
            (day, pin_id, currency, category, description.strip(), money_cents(amount), utc_now()))
    return cursor.lastrowid


def set_hourly_rate(storage, currency, amount):
    currency = valid_currency(currency)
    cents = money_cents(amount)
    with storage.conn:
        storage.conn.execute(
            """INSERT INTO labor_rates(currency,hourly_cents,updated_at) VALUES(?,?,?)
               ON CONFLICT(currency) DO UPDATE SET
               hourly_cents=excluded.hourly_cents,updated_at=excluded.updated_at""",
            (currency, cents, utc_now()))


def labor_summary(storage, currency):
    """Current configured hourly rate applied to all logged time; NOT a historical rate."""
    currency = valid_currency(currency)
    rate_row = storage.conn.execute(
        "SELECT hourly_cents FROM labor_rates WHERE currency=?", (currency,)).fetchone()
    rows = storage.conn.execute(
        """SELECT pin_id,SUM(seconds) FROM time_entries
           GROUP BY pin_id ORDER BY pin_id""").fetchall()
    if rate_row is None:
        return {"rate_configured": False, "seconds": sum(seconds for _, seconds in rows),
                "cost_cents": None, "by_pin": {}}
    rate = rate_row[0]
    by_pin = {}
    for pin_id, seconds in rows:
        cost = int((Decimal(seconds) * Decimal(rate) / Decimal(3600)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP))
        by_pin[pin_id] = {"seconds": seconds, "cost_cents": cost}
    return {"rate_configured": True, "hourly_cents": rate,
            "seconds": sum(seconds for _, seconds in rows),
            "cost_cents": sum(item["cost_cents"] for item in by_pin.values()),
            "by_pin": by_pin}


def cost_summary(storage, currency):
    currency = valid_currency(currency)
    rows = storage.conn.execute(
        """SELECT category,pin_id,SUM(amount_cents)
           FROM cost_entries WHERE currency=? GROUP BY category,pin_id""",
        (currency,)).fetchall()
    by_pin = {}
    for category, pin_id, cents in rows:
        key = pin_id
        if key not in by_pin:
            by_pin[key] = {"DIRECT": 0, "ALLOCATED": 0}
        by_pin[key][category] += cents
    return {"by_pin": by_pin,
            "direct_cents": sum(x["DIRECT"] for x in by_pin.values()),
            "allocated_cents": sum(x["ALLOCATED"] for x in by_pin.values())}
