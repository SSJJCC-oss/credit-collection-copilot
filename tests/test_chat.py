"""Tests for the helper functions in cli/chat.py. No API key needed."""
from google.adk.events import Event
from google.genai import types

from cli.chat import audit_since, last_audit_id, print_trace_event, short
from copilot.store import connect_store, log_event


def test_short_keeps_one_line_and_cuts_long_text():
    assert short({"order_no": "SO-026777"}) == '{"order_no": "SO-026777"}'
    assert short("a\nb   c") == "a b c"
    long_text = short("x" * 500, limit=20)
    assert len(long_text) == 20 and long_text.endswith("...")


def test_audit_entries_since_a_point(tmp_path):
    store = connect_store(tmp_path / "copilot_test.db")
    log_event(store, "copilot", "get_briefing")
    before = last_audit_id(store)
    log_event(store, "copilot", "review_order", {"order_no": "SO-026777"}, "HOLD")
    new = audit_since(store, before)
    store.close()
    assert [e["action"] for e in new] == ["review_order"]


def test_trace_prints_tool_calls(capsys):
    call = types.Part(function_call=types.FunctionCall(name="review_order", args={"order_no": "SO-026777"}))
    print_trace_event(Event(author="credit_agent", content=types.Content(role="model", parts=[call])))
    assert "credit_agent -> calls review_order" in capsys.readouterr().out