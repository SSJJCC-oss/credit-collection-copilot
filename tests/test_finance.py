"""Tests for copilot/finance.py - no API key needed."""
import pytest

from copilot.db import connect_billing_readonly, get_as_of_date
from copilot.finance import BUCKETS, age_bucket, ageing_summary, get_open_invoices


@pytest.mark.parametrize("days, expected", [
    (-10, "not_due"), (0, "not_due"),
    (1, "1-30"), (30, "1-30"),
    (31, "31-60"), (60, "31-60"),
    (61, "61-90"), (90, "61-90"),
    (91, "90+"), (700, "90+"),
])
def test_age_bucket_edges(days, expected):
    assert age_bucket(days) == expected


def test_ageing_summary_adds_up_by_bucket():
    invoices = [
        {"balance": 100.0, "bucket": "1-30"},
        {"balance": 50.5, "bucket": "1-30"},
        {"balance": 900.0, "bucket": "90+"},
    ]
    summary = ageing_summary(invoices)
    assert summary["1-30"] == {"amount": 150.5, "invoices": 2}
    assert summary["90+"] == {"amount": 900.0, "invoices": 1}
    assert summary["not_due"] == {"amount": 0.0, "invoices": 0}
    assert list(summary) == BUCKETS


def test_open_invoices_on_demo_data():
    con = connect_billing_readonly()
    invoices = get_open_invoices(con, get_as_of_date(con))
    con.close()
    assert len(invoices) == 1627
    assert all(inv["balance"] > 0 for inv in invoices)
    assert round(sum(inv["balance"] for inv in invoices)) == 4264941