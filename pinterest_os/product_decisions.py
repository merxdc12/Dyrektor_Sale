"""Conservative, explainable decision support. Never auto-stop a product.

Rules are policy heuristics, NOT validated forecasts. Incomplete evidence
always yields TEST. SCALE requires positive contribution and sufficient
observed conversions; STOP is never automatic.
"""
from .product_profitability import product_profitability


def evaluate_product(item, *, min_visits=100, min_conversions=5):
    reasons = []
    if item["labor_cents"] is None:
        return {"decision": "TEST", "reason": "Hourly labor rate missing; contribution/ROI unknown.",
                "evidence": "INCOMPLETE"}
    if item["visits"] < min_visits or item["conversions"] < min_conversions:
        return {"decision": "TEST",
                "reason": f"Limited attributed evidence: {item['visits']} visits and {item['conversions']} conversions; policy minimum {min_visits}/{min_conversions}.",
                "evidence": "LIMITED"}
    contribution = item["estimated_contribution_cents"]
    if contribution > 0:
        return {"decision": "SCALE",
                "reason": "Positive estimated contribution with minimum observed activity; validate attribution and costs before investment.",
                "evidence": "THRESHOLD_MET"}
    if contribution == 0:
        return {"decision": "OPTIMIZE",
                "reason": "Estimated contribution is zero; investigate costs and conversion economics.",
                "evidence": "THRESHOLD_MET"}
    return {"decision": "OPTIMIZE",
            "reason": "Negative estimated contribution; investigate pricing, attribution and costs. STOP requires human review.",
            "evidence": "THRESHOLD_MET"}


def decision_report(storage, currency="USD", *, min_visits=100, min_conversions=5):
    if not isinstance(min_visits, int) or min_visits <= 0:
        raise ValueError("min_visits must be a positive integer")
    if not isinstance(min_conversions, int) or min_conversions <= 0:
        raise ValueError("min_conversions must be a positive integer")
    result = []
    for item in product_profitability(storage, currency):
        decision = evaluate_product(item, min_visits=min_visits, min_conversions=min_conversions)
        result.append({**item, **decision})
    return result
