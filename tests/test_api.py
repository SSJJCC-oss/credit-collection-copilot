"""Tests for the web API (api/main.py). Uses FastAPI's test client - no server, no API key needed."""
import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A test client whose copilot store is a temporary file, not the real data/copilot.db."""
    monkeypatch.setenv("COPILOT_DB", str(tmp_path / "copilot_test.db"))
    monkeypatch.setenv("DRY_RUN", "true")
    return TestClient(app)


def test_health(client):
    body = client.get("/api/health").json()
    assert body == {"status": "ok", "as_of": "2026-10-25", "currency": "AED", "dry_run": True}


def test_briefing(client):
    assert round(client.get("/api/briefing").json()["total_owed"]) == 4264941


def test_pending_orders_have_decisions(client):
    body = client.get("/api/orders/pending").json()
    assert body["count"] == 15
    decisions = [o["decision"] for o in body["orders"]]
    assert decisions.count("HOLD") == 6 and decisions.count("REVIEW") == 3


def test_review_one_order_and_unknown_order(client):
    assert client.get("/api/orders/SO-026777/review").json()["decision"] == "HOLD"
    assert client.get("/api/orders/SO-999999/review").status_code == 404


def test_ambiguous_customer_is_a_400(client):
    response = client.get("/api/customers/Golden Palm")
    assert response.status_code == 400
    assert "matches" in response.json()["detail"]


def test_draft_then_human_approval_is_only_logged(client):
    draft = client.post("/api/drafts", json={"customer_name": "Golden Palm Catering"}).json()
    assert draft["status"] == "draft"
    assert client.get("/api/drafts").json()["count"] == 1

    decided = client.post(f"/api/drafts/{draft['id']}/decision",
                          json={"approve": True, "decided_by": "Fatima (manager)"}).json()
    assert decided["status"] == "logged"                      # DRY_RUN: never sent

    again = client.post(f"/api/drafts/{draft['id']}/decision",
                        json={"approve": False, "decided_by": "Ahmed"})
    assert again.status_code == 400                           # cannot decide twice

    actions = [e["action"] for e in client.get("/api/audit").json()["entries"]]
    assert actions[0] == "approve_draft" and "create_draft" in actions


def test_decision_needs_a_person(client):
    draft = client.post("/api/drafts", json={"customer_name": "Golden Palm Catering"}).json()
    missing = client.post(f"/api/drafts/{draft['id']}/decision", json={"approve": True})
    assert missing.status_code == 422                         # decided_by is required
    blank = client.post(f"/api/drafts/{draft['id']}/decision", json={"approve": True, "decided_by": " "})
    assert blank.status_code == 400

def test_dashboard_page_is_served(client):
    page = client.get("/")
    assert page.status_code == 200
    assert "Credit &amp; Collections Copilot" in page.text
    assert client.get("/app.js").status_code == 200
    assert client.get("/api/health").json()["status"] == "ok"    # API routes still work

# ---- /api/chat: the real agents need Gemini, so these tests swap in a fake runner ----

from google.adk.events import Event  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.genai import types  # noqa: E402

import api.main  # noqa: E402
from copilot import tools  # noqa: E402


class FakeRunner:
    """Behaves like ADK's runner: the router 'calls' credit_agent, a real tool runs, then it answers."""
    def __init__(self):
        self.session_service = InMemorySessionService()

    async def run_async(self, user_id, session_id, new_message):
        call = types.Part(function_call=types.FunctionCall(name="credit_agent", args={"request": "SO-026777"}))
        yield Event(author="copilot_router", content=types.Content(role="model", parts=[call]))
        tools.review_order("SO-026777")                      # writes a real audit-log line
        answer = types.Part(text="Decision: HOLD.")
        yield Event(author="copilot_router", content=types.Content(role="model", parts=[answer]))


@pytest.fixture
def fake_chat(client, monkeypatch):
    monkeypatch.setattr(api.main, "runner", FakeRunner())
    return client


def test_chat_returns_answer_specialist_and_tools(fake_chat):
    body = fake_chat.post("/api/chat", json={"message": "Should we approve SO-026777?"}).json()
    assert body["answer"] == "Decision: HOLD."
    assert body["specialists"] == ["credit_agent"]
    assert body["tools_used"][0]["tool"] == "review_order" and body["tools_used"][0]["ok"] is True
    assert body["session_id"]


def test_chat_keeps_the_same_conversation(fake_chat):
    first = fake_chat.post("/api/chat", json={"message": "Hello"}).json()
    second = fake_chat.post("/api/chat", json={"message": "And again", "session_id": first["session_id"]}).json()
    assert second["session_id"] == first["session_id"]


def test_empty_chat_message_is_refused(fake_chat):
    assert fake_chat.post("/api/chat", json={"message": ""}).status_code == 422