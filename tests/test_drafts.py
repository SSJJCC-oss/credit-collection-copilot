"""Tests for reminder drafts and human approval (store.py + reminders.py). No API key needed."""
import pytest

from copilot.db import connect_billing_readonly, get_as_of_date
from copilot.reminders import draft_reminder
from copilot.store import connect_store, decide_draft, get_draft, list_drafts, recent_audit


@pytest.fixture
def billing():
    con = connect_billing_readonly()
    yield con
    con.close()


@pytest.fixture
def store(tmp_path):
    con = connect_store(tmp_path / "copilot_test.db")
    yield con
    con.close()


@pytest.fixture
def draft(billing, store):
    """A real draft for Golden Palm Catering (customer 12)."""
    return draft_reminder(billing, store, 12, get_as_of_date(billing))


def test_draft_is_saved_waiting_for_approval(draft, store):
    assert draft["status"] == "draft"
    assert draft["customer_name"] == "Golden Palm Catering"
    assert draft["channel"] == "email"
    assert draft["language"] == "en"                       # from the shop's profile
    assert len(draft["invoice_refs"]) > 0
    assert get_draft(store, draft["id"])["subject"] == draft["subject"]
    assert recent_audit(store)[0]["action"] == "create_draft"


def test_no_duplicate_drafts_for_the_same_shop(draft, billing, store):
    again = draft_reminder(billing, store, 12, get_as_of_date(billing))
    assert again["already_existed"] is True
    assert again["id"] == draft["id"]
    assert len(list_drafts(store)) == 1


def test_approve_in_dry_run_is_only_logged(draft, store):
    decided = decide_draft(store, draft["id"], approve=True, decided_by="Fatima (manager)", dry_run=True)
    assert decided["status"] == "logged"
    assert decided["decided_by"] == "Fatima (manager)"
    last = recent_audit(store)[0]
    assert (last["actor"], last["action"], last["result"]) == ("Fatima (manager)", "approve_draft", "logged")


def test_approve_without_dry_run(draft, store):
    assert decide_draft(store, draft["id"], True, "Fatima", dry_run=False)["status"] == "approved"


def test_reject(draft, store):
    decided = decide_draft(store, draft["id"], False, "Fatima", dry_run=True, note="Shop paid by cheque")
    assert decided["status"] == "rejected"
    assert decided["decision_note"] == "Shop paid by cheque"


def test_cannot_decide_twice(draft, store):
    decide_draft(store, draft["id"], True, "Fatima", dry_run=True)
    with pytest.raises(ValueError, match="already decided"):
        decide_draft(store, draft["id"], False, "Ahmed", dry_run=True)


def test_decision_needs_a_person(draft, store):
    with pytest.raises(ValueError):
        decide_draft(store, draft["id"], True, "   ", dry_run=True)


def test_list_drafts_by_status(draft, billing, store):
    other = draft_reminder(billing, store, 211, get_as_of_date(billing))   # Bright Day Hypermarket
    decide_draft(store, draft["id"], True, "Fatima", dry_run=True)
    assert [d["id"] for d in list_drafts(store, "draft")] == [other["id"]]
    assert [d["id"] for d in list_drafts(store, "logged")] == [draft["id"]]


def test_arabic_preference_is_used(billing, store):
    d = draft_reminder(billing, store, 211, get_as_of_date(billing))       # prefers Arabic
    assert d["language"] == "ar"
    assert d["subject"].startswith("تذكير بالدفع")


def test_shop_with_nothing_overdue_gets_no_draft(billing, store):
    with pytest.raises(ValueError):
        draft_reminder(billing, store, 2, get_as_of_date(billing))          # Pearl Bakery
    assert list_drafts(store) == []