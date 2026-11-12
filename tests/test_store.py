"""Tests for copilot/store.py - uses a temporary database, never the real one. No API key needed."""
import json
import sqlite3

import pytest

from copilot.credit_rules import RULES_VERSION, review_order
from copilot.db import connect_billing_readonly, get_as_of_date
from copilot.store import connect_store, log_event, recent_audit, save_order_review


@pytest.fixture
def store(tmp_path):
    """A brand-new, empty copilot database in a temporary folder."""
    con = connect_store(tmp_path / "copilot_test.db")
    yield con
    con.close()


def test_tables_are_created(store):
    tables = {r[0] for r in store.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"reminder_drafts", "order_reviews", "audit_log"} <= tables


def test_connecting_twice_keeps_existing_data(tmp_path):
    path = tmp_path / "copilot_test.db"
    con = connect_store(path)
    log_event(con, "tester", "first_event")
    con.close()
    con = connect_store(path)                      # tables already exist: must not be wiped
    assert len(recent_audit(con)) == 1
    con.close()


def test_order_review_is_saved_with_its_reasons(store):
    billing = connect_billing_readonly()
    as_of = get_as_of_date(billing)
    review = review_order(billing, "SO-026777", as_of)
    billing.close()

    row_id = save_order_review(store, review, as_of, RULES_VERSION)
    row = store.execute("SELECT * FROM order_reviews WHERE id = ?", (row_id,)).fetchone()
    assert row["recommendation"] == "HOLD"
    assert row["rules_version"] == RULES_VERSION
    reasons = json.loads(row["reasons"])
    assert [r["rule"] for r in reasons] == ["credit_limit", "overdue", "payment_history"]


def test_database_refuses_an_invalid_recommendation(store):
    bad = {"order_no": "SO-1", "customer_id": 1, "decision": "MAYBE", "reasons": []}
    with pytest.raises(sqlite3.IntegrityError):
        save_order_review(store, bad, "2026-10-25", RULES_VERSION)


def test_audit_log_newest_first(store):
    log_event(store, "credit_agent", "review_order", {"order_no": "SO-026777"}, "HOLD", True, 12)
    log_event(store, "data_qa_agent", "run_safe_query", {"sql": "DELETE FROM customers"},
              "refused", ok=False)
    entries = recent_audit(store)
    assert [e["action"] for e in entries] == ["run_safe_query", "review_order"]
    assert entries[0]["ok"] == 0
    assert json.loads(entries[1]["arguments"]) == {"order_no": "SO-026777"}