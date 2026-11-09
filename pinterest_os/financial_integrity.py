"""Conservative reconciliation flags; ambiguity is NOT automatically deduplicated."""


def reconciliation_flags(storage, currency):
    """Detect possible double count on matching date/pin/currency.

    CSV reported_cost_cents is aggregated and has no expense-level ID,
    so overlapping records are flagged for human review, not subtracted.
    """
    rows = storage.conn.execute(
        """SELECT b.date,b.pin_id,b.reported_cost_cents,
                  COUNT(c.id),COALESCE(SUM(c.amount_cents),0)
           FROM business_metrics b
           JOIN cost_entries c ON c.date=b.date AND c.pin_id=b.pin_id
                AND c.currency=b.currency
           WHERE b.currency=? AND b.reported_cost_cents>0
           GROUP BY b.date,b.pin_id,b.reported_cost_cents
           ORDER BY b.date,b.pin_id""", (currency,)).fetchall()
    return [
        {"date": day, "pin_id": pin_id, "reported_cost_cents": reported,
         "ledger_entries": count, "ledger_cost_cents": ledger,
         "issue": "POSSIBLE_DOUBLE_COUNT"}
        for day, pin_id, reported, count, ledger in rows
    ]


def unresolved_product_ids(storage, currency):
    """Products with ambiguous reported/ledger cost overlap."""
    flags = reconciliation_flags(storage, currency)
    mapping = dict(storage.conn.execute("SELECT id,product_id FROM pins").fetchall())
    return {mapping.get(flag["pin_id"]) for flag in flags}
