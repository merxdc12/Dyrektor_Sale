"""Product-level contribution estimates, never verified net profit.

All attribution uses CURRENT pin.product_id. Unassigned costs and time are
not silently allocated. Business CSV reported costs and ledger costs are
assumed distinct; operators must avoid entering the same expense twice.
"""
from .profit_costs import cost_summary, labor_summary, valid_currency
from .financial_integrity import unresolved_product_ids, duplicate_ledger_adjustments


def product_profitability(storage, currency):
    currency = valid_currency(currency)
    revenue_rows = storage.conn.execute(
        """SELECT p.product_id,SUM(b.revenue_cents),SUM(b.reported_cost_cents),
                  SUM(b.site_visits),SUM(b.conversions)
           FROM business_metrics b JOIN pins p ON p.id=b.pin_id
           WHERE b.currency=? GROUP BY p.product_id""", (currency,)).fetchall()
    results = {}
    def entry(product_id):
        if product_id not in results:
            results[product_id] = {
                "product_id": product_id, "revenue_cents": 0,
                "reported_cost_cents": 0, "direct_cents": 0,
                "allocated_cents": 0, "labor_cents": None,
                "visits": 0, "conversions": 0}
        return results[product_id]
    for product_id, revenue, reported, visits, conversions in revenue_rows:
        item = entry(product_id)
        item.update(revenue_cents=revenue, reported_cost_cents=reported,
                    visits=visits, conversions=conversions)
    mapping = {row[0]: row[1] for row in storage.conn.execute(
        "SELECT id,product_id FROM pins")}
    costs = cost_summary(storage, currency)
    for pin_id, amounts in costs["by_pin"].items():
        item = entry(mapping.get(pin_id))
        item["direct_cents"] += amounts["DIRECT"]
        item["allocated_cents"] += amounts["ALLOCATED"]
    labor = labor_summary(storage, currency)
    if labor["rate_configured"]:
        for pin_id, details in labor["by_pin"].items():
            item = entry(mapping.get(pin_id))
            item["labor_cents"] = (item["labor_cents"] or 0) + details["cost_cents"]
    names = {row[0]: row[1] for row in storage.conn.execute(
        "SELECT id,name FROM products")}
    flagged_products = unresolved_product_ids(storage, currency)
    duplicate_adjustments = duplicate_ledger_adjustments(storage, currency)
    adjustment_by_product = {}
    for pin_id, cents in duplicate_adjustments.items():
        product_id = mapping.get(pin_id)
        adjustment_by_product[product_id] = adjustment_by_product.get(product_id, 0) + cents
    output = []
    for product_id, item in results.items():
        item["product_name"] = names.get(product_id, "Unassigned")
        item["reconciliation_required"] = product_id in flagged_products
        if labor["rate_configured"]:
            item["labor_cents"] = item["labor_cents"] or 0
        known_cost = (item["reported_cost_cents"] + item["direct_cents"]
                      + item["allocated_cents"])
        item["reconciled_duplicate_cents"] = adjustment_by_product.get(product_id, 0)
        known_cost -= item["reconciled_duplicate_cents"]
        item["known_cost_cents"] = known_cost
        item["nonlabor_contribution_cents"] = item["revenue_cents"] - known_cost
        if item["labor_cents"] is None or item["reconciliation_required"]:
            item["estimated_contribution_cents"] = None
            item["roi_percent"] = None
        else:
            total = known_cost + item["labor_cents"]
            contribution = item["revenue_cents"] - total
            item["estimated_contribution_cents"] = contribution
            item["roi_percent"] = (100.0 * contribution / total) if total else None
        output.append(item)
    return sorted(output, key=lambda item: (
        item["estimated_contribution_cents"] is None,
        -(item["estimated_contribution_cents"] or 0),
        item["product_name"]))
