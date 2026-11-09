"""Human-reviewed cost overlap reconciliation; never silently deduplicate."""
import hashlib
import json
from .storage import utc_now


def _fingerprint(reported, entries):
    payload = [reported, [list(row) for row in entries]]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()


def reconciliation_flags(storage, currency):
    rows = storage.conn.execute(
        """SELECT b.date,b.pin_id,b.reported_cost_cents
           FROM business_metrics b WHERE b.currency=? AND b.reported_cost_cents>0
           AND EXISTS(SELECT 1 FROM cost_entries c WHERE c.date=b.date
                      AND c.pin_id=b.pin_id AND c.currency=b.currency)
           ORDER BY b.date,b.pin_id""", (currency,)).fetchall()
    output = []
    for day, pin_id, reported in rows:
        entries = storage.conn.execute(
            """SELECT id,amount_cents,category,description,source_ref
               FROM cost_entries WHERE date=? AND pin_id=? AND currency=?
               ORDER BY id""", (day, pin_id, currency)).fetchall()
        fingerprint = _fingerprint(reported, entries)
        review = storage.conn.execute(
            """SELECT decision,note,fingerprint FROM reconciliation_reviews
               WHERE date=? AND pin_id=? AND currency=?""",
            (day, pin_id, currency)).fetchone()
        decision = review[0] if review and review[2] == fingerprint else None
        output.append({
            "date": day, "pin_id": pin_id, "currency": currency,
            "reported_cost_cents": reported, "ledger_entries": len(entries),
            "ledger_cost_cents": sum(row[1] for row in entries),
            "fingerprint": fingerprint, "decision": decision,
            "note": review[1] if decision else "",
            "issue": "REVIEWED" if decision else "POSSIBLE_DOUBLE_COUNT"})
    return output


def record_review(storage, currency, day, pin_id, decision, note):
    if decision not in ("DISTINCT", "DUPLICATE"):
        raise ValueError("Choose DISTINCT or DUPLICATE")
    if not note or not note.strip():
        raise ValueError("A documented reason is required")
    matching = [flag for flag in reconciliation_flags(storage, currency)
                if flag["date"] == day and flag["pin_id"] == pin_id]
    if len(matching) != 1:
        raise ValueError("No matching overlap to review")
    flag = matching[0]
    with storage.conn:
        storage.conn.execute(
            """INSERT INTO reconciliation_reviews
               (date,pin_id,currency,fingerprint,decision,note,reviewed_at)
               VALUES(?,?,?,?,?,?,?)
               ON CONFLICT(date,pin_id,currency) DO UPDATE SET
               fingerprint=excluded.fingerprint,decision=excluded.decision,
               note=excluded.note,reviewed_at=excluded.reviewed_at""",
            (day, pin_id, currency, flag["fingerprint"], decision, note.strip(), utc_now()))


def unresolved_product_ids(storage, currency):
    mapping = dict(storage.conn.execute("SELECT id,product_id FROM pins"))
    return {mapping.get(flag["pin_id"]) for flag in reconciliation_flags(storage, currency)
            if flag["decision"] is None}


def duplicate_ledger_adjustments(storage, currency):
    """DUPLICATE means ALL same-day pin ledger costs are already in CSV."""
    result = {}
    for flag in reconciliation_flags(storage, currency):
        if flag["decision"] == "DUPLICATE":
            result[flag["pin_id"]] = result.get(flag["pin_id"], 0) + flag["ledger_cost_cents"]
    return result
