"""Tests for copilot/credit_rules.py - no API key needed."""
import pytest

from copilot.credit_rules import decide, list_pending_orders, review_order
from copilot.db import connect_billing_readonly, get_as_of_date


def make_facts(**changes):
    """A healthy shop and a normal order; each test changes only what it is testing."""
    facts = {"total": 1000.0, "credit_limit": 20000.0, "owed": 2000.0, "headroom": 18000.0,
             "worst_days_overdue": 0, "usual_order": 1000.0, "avg_days_late": 5.0}
    facts.update(changes)
    return facts


def rules_fired(result):
    return [r["rule"] for r in result["reasons"]]


def test_healthy_shop_is_approved():
    result = decide(make_facts())
    assert result["decision"] == "APPROVE"
    assert rules_fired(result) == ["all_clear"]


def test_over_credit_limit_is_hold():
    result = decide(make_facts(owed=19500.0))          # 19,500 + 1,000 > 20,000
    assert result["decision"] == "HOLD"
    assert "credit_limit" in rules_fired(result)


@pytest.mark.parametrize("days, expected", [
    (60, "APPROVE"), (61, "REVIEW"), (90, "REVIEW"), (91, "HOLD"),
])
def test_overdue_edges(days, expected):
    assert decide(make_facts(worst_days_overdue=days))["decision"] == expected


@pytest.mark.parametrize("total, expected", [(2000.0, "APPROVE"), (2001.0, "REVIEW")])
def test_order_size_edge(total, expected):
    assert decide(make_facts(total=total))["decision"] == expected


def test_slow_payer_is_review():
    result = decide(make_facts(avg_days_late=50.0))
    assert result["decision"] == "REVIEW"
    assert rules_fired(result) == ["payment_history"]


def test_hold_beats_review_and_all_reasons_are_kept():
    result = decide(make_facts(owed=19500.0, total=3000.0))   # over limit AND 3x usual
    assert result["decision"] == "HOLD"
    assert rules_fired(result) == ["credit_limit", "order_size"]


def test_new_shop_without_history_does_not_crash():
    result = decide(make_facts(usual_order=None, avg_days_late=None))
    assert result["decision"] == "APPROVE"


# The 12 orders created by scripts/seed_demo.py, with the answer each group was designed for.
SEEDED = {
    "SO-026771": "APPROVE", "SO-026772": "APPROVE", "SO-026773": "APPROVE",
    "SO-026774": "REVIEW",  "SO-026775": "REVIEW",  "SO-026776": "REVIEW",
    "SO-026777": "HOLD",    "SO-026778": "HOLD",    "SO-026779": "HOLD",
    "SO-026780": "HOLD",    "SO-026781": "HOLD",    "SO-026782": "HOLD",
}


@pytest.mark.parametrize("order_no, expected", SEEDED.items())
def test_seeded_orders_get_expected_decision(order_no, expected):
    con = connect_billing_readonly()
    result = review_order(con, order_no, get_as_of_date(con))
    con.close()
    assert result["decision"] == expected


def test_pending_orders_list_has_all_15():
    con = connect_billing_readonly()
    assert len(list_pending_orders(con)) == 15
    con.close()


def test_unknown_order_gives_clear_error():
    con = connect_billing_readonly()
    with pytest.raises(ValueError):
        review_order(con, "SO-999999", "2026-10-25")
    con.close()