"""Tests for how the agents are wired together. They check structure only, so no API key is needed."""
import inspect

from agents.copilot_agent.agent import root_agent
from copilot import tools

SPECIALISTS = {t.agent.name: t.agent for t in root_agent.tools}


def tool_names(agent):
    return {f.__name__ for f in agent.tools}


def test_router_has_the_four_specialists():
    assert set(SPECIALISTS) == {"briefing_agent", "credit_agent", "collections_agent", "data_qa_agent"}


def test_each_specialist_only_has_its_own_tools():
    assert tool_names(SPECIALISTS["briefing_agent"]) == {"get_briefing", "find_quiet_shops"}
    assert tool_names(SPECIALISTS["credit_agent"]) == {"list_pending_orders", "review_order",
                                                        "get_customer_overview"}
    assert tool_names(SPECIALISTS["collections_agent"]) == {"get_overdue_invoices", "draft_reminder",
                                                             "list_drafts"}
    assert tool_names(SPECIALISTS["data_qa_agent"]) == {"describe_schema", "run_safe_query"}


def test_every_tool_is_used_and_nothing_else():
    public_tools = {n for n, f in inspect.getmembers(tools, inspect.isfunction)
                    if f.__module__ == tools.__name__ and not n.startswith("_") and n != "find_customer"}
    used = set().union(*(tool_names(a) for a in SPECIALISTS.values()))
    assert used == public_tools


def test_only_the_data_agent_can_run_sql():
    for name, agent in SPECIALISTS.items():
        if name != "data_qa_agent":
            assert "run_safe_query" not in tool_names(agent)