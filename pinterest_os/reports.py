"""Offline reporting. CSV exports use current attribution and never claim net profit."""
import csv
from pathlib import Path
from decimal import Decimal
from .product_profitability import product_profitability
from .product_decisions import decision_report
from .financial_integrity import reconciliation_flags
from .profit_costs import valid_currency


FIELDS = ("product_id", "product_name", "currency", "visits", "conversions",
          "revenue", "reported_cost", "direct_cost", "allocated_cost",
          "reconciled_duplicate_cost", "labor_estimate", "known_cost",
          "estimated_contribution", "roi_percent", "reconciliation_required",
          "decision", "evidence", "reason")


def _money(cents):
    return "" if cents is None else str((Decimal(cents) / 100).quantize(Decimal("0.01")))


def report_rows(storage, currency="USD"):
    currency = valid_currency(currency)
    decisions = {row["product_id"]: row for row in decision_report(storage, currency)}
    output = []
    for item in product_profitability(storage, currency):
        decision = decisions[item["product_id"]]
        output.append(dict(
            product_id=item["product_id"] if item["product_id"] is not None else "",
            product_name=item["product_name"], currency=currency,
            visits=item["visits"], conversions=item["conversions"],
            revenue=_money(item["revenue_cents"]),
            reported_cost=_money(item["reported_cost_cents"]),
            direct_cost=_money(item["direct_cents"]),
            allocated_cost=_money(item["allocated_cents"]),
            reconciled_duplicate_cost=_money(item["reconciled_duplicate_cents"]),
            labor_estimate=_money(item["labor_cents"]),
            known_cost=_money(item["known_cost_cents"]),
            estimated_contribution=_money(item["estimated_contribution_cents"]),
            roi_percent="" if item["roi_percent"] is None else format(item["roi_percent"], ".2f"),
            reconciliation_required=item["reconciliation_required"],
            decision=decision["decision"], evidence=decision["evidence"],
            reason=decision["reason"]))
    return output


def _safe_csv_cell(value):
    """Prevent spreadsheet applications from evaluating untrusted text as formulas."""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\\t", "\\r")):
        return "'" + value
    return value


def export_report(storage, path, currency="USD"):
    """Export explicit per-product estimates; never overwrite an existing file."""
    rows = report_rows(storage, currency)
    destination = Path(path)
    with destination.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows([{key: _safe_csv_cell(value) for key, value in row.items()} for row in rows])
    return len(rows)


def report_warnings(storage, currency="USD"):
    flags = reconciliation_flags(storage, valid_currency(currency))
    return {"overlaps": len(flags),
            "unresolved": sum(flag["decision"] is None for flag in flags)}
