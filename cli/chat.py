"""chat.py - talk to the copilot in the terminal. Add --trace to see every agent and tool call.

Run from the project folder:
    python -m cli.chat
    python -m cli.chat --trace
"""
import argparse
import asyncio
import json
import sqlite3

from google.adk.runners import InMemoryRunner
from google.genai import types

from agents.copilot_agent.agent import root_agent
from copilot.store import connect_store

APP_NAME = "credit_collections_copilot"
USER_ID = "manager"
EXIT_WORDS = {"exit", "quit", "bye"}


def short(value, limit: int = 120) -> str:
    """Turn any value into one line of text, cut to `limit` characters."""
    text = value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def last_audit_id(con: sqlite3.Connection) -> int:
    """The id of the newest audit-log entry (0 if the log is empty)."""
    return con.execute("SELECT COALESCE(MAX(id), 0) FROM audit_log").fetchone()[0]


def audit_since(con: sqlite3.Connection, after_id: int) -> list[dict]:
    """Audit-log entries written after `after_id`, oldest first."""
    rows = con.execute("SELECT * FROM audit_log WHERE id > ? ORDER BY id", (after_id,)).fetchall()
    return [dict(r) for r in rows]


def print_trace_event(event) -> None:
    """Print the agent and tool calls inside one ADK event, one line each."""
    for call in event.get_function_calls():
        print(f"  [trace] {event.author} -> calls {call.name}({short(call.args)})")
    for response in event.get_function_responses():
        print(f"  [trace] {response.name} -> returned {short(response.response)}")


async def ask(runner: InMemoryRunner, session_id: str, question: str, trace: bool) -> str:
    """Send one question to the router and return its final answer as text."""
    message = types.Content(role="user", parts=[types.Part(text=question)])
    answer = ""
    async for event in runner.run_async(user_id=USER_ID, session_id=session_id, new_message=message):
        if trace:
            print_trace_event(event)
        if event.is_final_response() and event.content and event.content.parts:
            answer = "".join(p.text for p in event.content.parts if p.text and not p.thought)
    return answer


async def main(trace: bool) -> None:
    runner = InMemoryRunner(agent=root_agent, app_name=APP_NAME)
    session = await runner.session_service.create_session(app_name=APP_NAME, user_id=USER_ID)
    store = connect_store()
    print("Credit & Collections Copilot. Ask a question, or type 'exit' to quit.")
    if trace:
        print("Trace mode is ON: every agent call, tool call and audit-log entry is shown.")

    while True:
        try:
            question = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not question:
            continue
        if question.lower() in EXIT_WORDS:
            break

        before = last_audit_id(store)
        try:
            answer = await ask(runner, session.id, question, trace)
        except Exception as error:          # e.g. login expired or Google unavailable: keep the chat alive
            print(f"\n[error] {error}")
            continue
        if trace:
            for entry in audit_since(store, before):
                status = "ok" if entry["ok"] else "FAILED"
                print(f"  [audit] {entry['action']}({short(json.loads(entry['arguments']), 80)}) "
                      f"{status} in {entry['duration_ms']} ms")
        print(f"\nCopilot: {answer}")

    store.close()
    print("Goodbye.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chat with the Credit & Collections Copilot.")
    parser.add_argument("--trace", action="store_true", help="show every agent and tool call")
    args = parser.parse_args()
    asyncio.run(main(args.trace))