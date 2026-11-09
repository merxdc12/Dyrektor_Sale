"""Decision policies are conservative and never auto-stop products."""
import pytest
from pinterest_os.product_decisions import evaluate_product, decision_report
from pinterest_os.storage import Storage


def sample(**changes):
    item = {"product_id": 1, "labor_cents": 100, "visits": 150,
            "conversions": 10, "estimated_contribution_cents": 500}
    item.update(changes)
    return item


def test_decisions():
    assert evaluate_product(sample())["decision"] == "SCALE"
    assert evaluate_product(sample(labor_cents=None))["decision"] == "TEST"
    assert evaluate_product(sample(product_id=None))["decision"] == "TEST"
    assert evaluate_product(sample(visits=5))["decision"] == "TEST"
    assert evaluate_product(sample(conversions=1))["decision"] == "TEST"
    assert evaluate_product(sample(estimated_contribution_cents=0))["decision"] == "OPTIMIZE"
    negative = evaluate_product(sample(estimated_contribution_cents=-100))
    assert negative["decision"] == "OPTIMIZE"
    assert "human review" in negative["reason"]


def test_report_threshold_validation(tmp_path):
    db = Storage(tmp_path / "decisions.sqlite3")
    try:
        assert decision_report(db) == []
        with pytest.raises(ValueError):
            decision_report(db, min_visits=0)
        with pytest.raises(ValueError):
            decision_report(db, min_conversions=-1)
    finally:
        db.close()
