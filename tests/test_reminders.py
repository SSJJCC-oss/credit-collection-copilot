"""Tests for copilot/reminders.py - no API key needed."""
import pytest

from copilot.db import connect_billing_readonly, get_as_of_date
from copilot.reminders import (build_reminder, choose_channel, get_customer_contact,
                               get_overdue_invoices, tone_for)

CONTACT = {"customer_id": 1, "customer_name": "Shop A", "contact_person": "Omar",
           "email": "omar@example.test", "phone": "+971 50 000 0000",
           "trn": "100123456789012", "language": "en", "rep_name": "Aisha Haddad"}


def make_invoices(*days_overdue):
    """Hand-made overdue invoices of AED 100 each, with the given days overdue."""
    return [{"order_no": f"SO-{i:06d}", "due_date": "2026-09-01", "balance": 100.0, "days_overdue": d}
            for i, d in enumerate(days_overdue, start=1)]


@pytest.mark.parametrize("days, expected", [(1, "gentle"), (30, "gentle"), (31, "firm"),
                                            (90, "firm"), (91, "final")])
def test_tone_edges(days, expected):
    assert tone_for(days) == expected


def test_english_reminder_uses_real_details():
    r = build_reminder(CONTACT, make_invoices(10, 45))
    assert r["amount_due"] == 200.0
    assert r["invoice_refs"] == ["SO-000001", "SO-000002"]
    assert "2 overdue invoice(s), AED 200.00" in r["subject"]
    for text in ["Dear Omar", "SO-000001", "SO-000002", "100123456789012", "Aisha Haddad"]:
        assert text in r["body"]
    assert r["tone"] == "firm"                              # oldest bill is 45 days late


def test_arabic_reminder():
    r = build_reminder(CONTACT, make_invoices(120), language="ar")
    assert r["subject"].startswith("تذكير بالدفع")
    assert "SO-000001" in r["body"]
    assert r["tone"] == "final"


def test_long_lists_are_shortened():
    r = build_reminder(CONTACT, make_invoices(*[5] * 15))
    assert r["body"].count("SO-0000") == 10
    assert "and 5 more overdue invoice(s)" in r["body"]
    assert r["amount_due"] == 1500.0                       # the total still covers all 15


def test_missing_trn_is_simply_left_out():
    r = build_reminder({**CONTACT, "trn": None}, make_invoices(5))
    assert "TRN" not in r["body"]


def test_no_overdue_invoices_gives_clear_error():
    with pytest.raises(ValueError):
        build_reminder(CONTACT, [])


def test_channel_choice():
    assert choose_channel(CONTACT) == ("email", "omar@example.test")
    assert choose_channel({**CONTACT, "email": None}) == ("sms", "+971 50 000 0000")
    assert choose_channel({**CONTACT, "email": None, "phone": None}) is None


def test_real_shop_reminder():
    con = connect_billing_readonly()
    as_of = get_as_of_date(con)
    contact = get_customer_contact(con, 12)                 # Golden Palm Catering
    invoices = get_overdue_invoices(con, 12, as_of)
    con.close()
    assert contact["customer_name"] == "Golden Palm Catering"
    assert all(inv["customer_id"] == 12 and inv["days_overdue"] > 0 for inv in invoices)
    r = build_reminder(contact, invoices)
    assert r["tone"] == "final"                             # its oldest bill is 660 days late
    assert invoices[0]["order_no"] in r["body"]