"""Tests for the briefing functions in copilot/finance.py - no API key needed."""
from copilot.db import connect_billing_readonly, get_as_of_date
from copilot.finance import build_briefing, over_limit_customers, summarise_by_customer, top_to_chase

# Three hand-made unpaid bills for two shops - small enough to check by hand.
SAMPLE = [
    {"customer_id": 1, "customer_name": "Shop A", "city": "Dubai",
     "balance": 1000.0, "days_overdue": 100, "bucket": "90+"},
    {"customer_id": 1, "customer_name": "Shop A", "city": "Dubai",
     "balance": 500.0, "days_overdue": -5, "bucket": "not_due"},
    {"customer_id": 2, "customer_name": "Shop B", "city": "Ajman",
     "balance": 3000.0, "days_overdue": 10, "bucket": "1-30"},
]


def test_summarise_by_customer():
    shops = summarise_by_customer(SAMPLE)
    a = shops[1]
    assert a["owed"] == 1500.0          # 1000 + 500
    assert a["overdue"] == 1000.0       # the 500 is not due yet
    assert a["worst_days_overdue"] == 100
    assert a["invoices"] == 2
    assert a["priority"] == 4000.0      # 1000 x weight 4 (90+) + 500 x weight 0


def test_top_to_chase_ranks_by_priority():
    ranked = top_to_chase(summarise_by_customer(SAMPLE))
    # Shop B owes more (3000) but is only 10 days late (priority 3000);
    # Shop A's 1000 is 100 days late (priority 4000), so A comes first.
    assert [s["customer_name"] for s in ranked] == ["Shop A", "Shop B"]
    assert len(top_to_chase(summarise_by_customer(SAMPLE), n=1)) == 1


def test_over_limit_customers():
    shops = summarise_by_customer(SAMPLE)
    over = over_limit_customers(shops, {1: 2000.0, 2: 2500.0})
    assert len(over) == 1
    assert over[0]["customer_name"] == "Shop B"
    assert over[0]["excess"] == 500.0


def test_briefing_on_demo_data():
    con = connect_billing_readonly()
    b = build_briefing(con, get_as_of_date(con))
    con.close()
    assert round(b["total_owed"]) == 4264941
    assert round(b["total_overdue"]) == 2429177
    assert len(b["over_limit"]) == 24
    assert b["top_to_chase"][0]["customer_name"] == "Harbor View Supermarket"
    assert b["pending_cheques"]["cheques"] == 87