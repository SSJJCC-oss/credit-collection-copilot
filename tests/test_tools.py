"""Tests for copilot/tools.py - the functions the AI agents may call. No API key needed."""
import inspect

import pytest

from copilot import tools
from copilot.store import connect_store, list_drafts, recent_audit


@pytest.fixture(autouse=True)
def temporary_store(tmp_path, monkeypatch):
    """Point COPILOT_DB at a temporary file, so tests never touch the real data/copilot.db."""
    path = tmp_path / "copilot_test.db"
    monkeypatch.setenv("COPILOT_DB", str(path))
    return path


def test_briefing_tool():
    b = tools.get_briefing()
    assert round(b["total_owed"]) == 4264941
    assert b["over_limit_count"] == 24 and len(b["over_limit"]) == 10


def test_review_order_tool_saves_and_logs(temporary_store):
    r = tools.review_order("so-026777 ")                 # messy input is cleaned up
    assert r["decision"] == "HOLD"
    store = connect_store(temporary_store)
    assert store.execute("SELECT COUNT(*) FROM order_reviews").fetchone()[0] == 1
    entry = recent_audit(store)[0]
    assert (entry["action"], entry["ok"]) == ("review_order", 1)
    store.close()


def test_unknown_order_returns_error_instead_of_crashing():
    assert "error" in tools.review_order("SO-999999")


def test_customer_lookup():
    assert tools.get_customer_overview("Golden Palm Catering")["credit_limit"] == 37000.0
    ambiguous = tools.get_customer_overview("Golden Palm")
    assert "matches" in ambiguous["error"]
    assert "No shop" in tools.get_customer_overview("Nowhere Shop")["error"]


def test_draft_reminder_tool_creates_a_draft_only(temporary_store):
    d = tools.draft_reminder("Golden Palm Catering")
    assert d["status"] == "draft"
    store = connect_store(temporary_store)
    assert len(list_drafts(store, "draft")) == 1
    store.close()
    assert tools.list_drafts()["count"] == 1


def test_unsafe_query_is_refused_and_logged(temporary_store):
    result = tools.run_safe_query("SELECT * FROM synthetic_notes")
    assert "synthetic_notes" in result["error"]
    store = connect_store(temporary_store)
    assert recent_audit(store)[0]["ok"] == 0
    store.close()


def test_no_tool_can_approve_reject_or_send():
    names = [n for n, f in inspect.getmembers(tools, inspect.isfunction) if f.__module__ == tools.__name__]
    for forbidden in ("approve", "reject", "decide", "send"):
        assert not any(forbidden in n for n in names), f"a tool name contains '{forbidden}'"