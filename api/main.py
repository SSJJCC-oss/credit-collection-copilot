"""main.py - the copilot's web API. Every screen (our dashboard, or BillCRM's own pages) talks to this.

Run from the project folder:
    uvicorn api.main:app --reload --port 8001
Then open http://127.0.0.1:8001/docs to see and try every endpoint.
"""
import base64
import os
import secrets

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from copilot import credit_rules, tools
from copilot.config import load_settings
from copilot.db import connect_billing_readonly, get_as_of_date
from copilot.store import connect_store, decide_draft, get_draft, log_event, recent_audit

app = FastAPI(
    title="Credit & Collections Copilot API",
    description="Read-only credit and collections insights, plus a human approval queue for reminders.",
    version="1.0",
)

# Which OTHER websites may call this API from a browser (e.g. BillCRM's pages). Empty = none.
allowed_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_methods=["GET", "POST"],
                   allow_headers=["*"])

# If DEMO_PASSWORD is set (e.g. on Cloud Run), every page and API call needs it.
# The browser shows its own login box; any username works, the password must match.
@app.middleware("http")
async def require_demo_password(request: Request, call_next):
    password = load_settings().demo_password
    if not password:                                   # no password set (e.g. on your laptop): open
        return await call_next(request)
    header = request.headers.get("authorization", "")
    if header.startswith("Basic "):
        try:
            _, _, given = base64.b64decode(header[6:]).decode().partition(":")
        except ValueError:
            given = ""
        if secrets.compare_digest(given.encode(), password.encode()):
            return await call_next(request)
    return Response("Login required", status_code=401,
                    headers={"WWW-Authenticate": 'Basic realm="Credit Copilot demo"'})


# ------------------------------------------------------------------------ request bodies

class DraftRequest(BaseModel):
    customer_name: str
    language: str = ""                 # "en", "ar", or empty for the shop's preference


class DraftDecision(BaseModel):
    approve: bool
    decided_by: str                    # the PERSON making the decision
    note: str = ""


# ------------------------------------------------------------------------------ helpers

def check(result: dict) -> dict:
    """Turn a tool's {"error": ...} into a proper HTTP error; otherwise pass the result through."""
    if "error" in result:
        message = result["error"]
        status = 404 if ("not found" in message or "No shop" in message) else 400
        raise HTTPException(status_code=status, detail=message)
    return result


# ---------------------------------------------------------------------------- endpoints

@app.get("/api/health")
def health() -> dict:
    """Is the API running, which data date is 'today', and is DRY_RUN on?"""
    settings = load_settings()
    billing = connect_billing_readonly()
    as_of = get_as_of_date(billing)
    billing.close()
    return {"status": "ok", "as_of": as_of, "currency": settings.currency, "dry_run": settings.dry_run}


@app.get("/api/briefing")
def briefing() -> dict:
    """Feature 1: today's credit and collections numbers."""
    return check(tools.get_briefing())


@app.get("/api/quiet-shops")
def quiet_shops(limit: int = 10) -> dict:
    """Feature 5: shops that have stopped ordering."""
    return check(tools.find_quiet_shops(limit))


@app.get("/api/orders/pending")
def pending_orders() -> dict:
    """Feature 2: every waiting order with its APPROVE / REVIEW / HOLD recommendation (not saved)."""
    billing = connect_billing_readonly()
    as_of = get_as_of_date(billing)
    orders = []
    for order in credit_rules.list_pending_orders(billing):
        review = credit_rules.review_order(billing, order["order_no"], as_of)
        orders.append({**order, "decision": review["decision"], "reasons": review["reasons"]})
    billing.close()
    store = connect_store()
    log_event(store, "dashboard", "pending_orders", {}, f"{len(orders)} orders")
    store.close()
    return {"as_of": as_of, "currency": load_settings().currency, "count": len(orders), "orders": orders}


@app.get("/api/orders/{order_no}/review")
def review(order_no: str) -> dict:
    """Feature 2: the full review of one order (saved in order_reviews and the audit log)."""
    return check(tools.review_order(order_no))


@app.get("/api/customers/{customer_name}")
def customer(customer_name: str) -> dict:
    """One shop's credit picture."""
    return check(tools.get_customer_overview(customer_name))


@app.get("/api/drafts")
def drafts(status: str = "draft") -> dict:
    """Feature 3: the reminder approval queue ('draft', 'logged', 'approved', 'rejected' or 'all')."""
    return check(tools.list_drafts(status))


@app.get("/api/drafts/{draft_id}")
def one_draft(draft_id: int) -> dict:
    """One reminder draft, including its full text."""
    store = connect_store()
    try:
        return get_draft(store, draft_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    finally:
        store.close()


@app.post("/api/drafts")
def create_draft(request: DraftRequest) -> dict:
    """Feature 3: write a reminder for one shop and add it to the approval queue. Nothing is sent."""
    return check(tools.draft_reminder(request.customer_name, request.language))


@app.post("/api/drafts/{draft_id}/decision")
def decide(draft_id: int, decision: DraftDecision) -> dict:
    """A PERSON approves or rejects a draft. With DRY_RUN on, an approved draft is only 'logged'."""
    store = connect_store()
    try:
        return decide_draft(store, draft_id, decision.approve, decision.decided_by,
                            load_settings().dry_run, decision.note)
    except ValueError as error:
        status = 404 if "not found" in str(error) else 400
        raise HTTPException(status_code=status, detail=str(error))
    finally:
        store.close()


@app.get("/api/audit")
def audit(limit: int = 50) -> dict:
    """The most recent actions taken by the copilot and by people, newest first."""
    store = connect_store()
    entries = recent_audit(store, limit)
    store.close()
    return {"count": len(entries), "entries": entries}

# ------------------------------------------------------------------- chat with the agents (6.4)
from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402
from pydantic import Field  # noqa: E402

from agents.copilot_agent.agent import root_agent  # noqa: E402
from cli.chat import audit_since, last_audit_id  # noqa: E402

CHAT_APP = "credit_collections_copilot"
CHAT_USER = "dashboard"
runner = InMemoryRunner(agent=root_agent, app_name=CHAT_APP)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None        # send back the id you received to continue the same conversation


@app.post("/api/chat")
async def chat(request: ChatRequest) -> dict:
    """Ask the multi-agent copilot a question in plain English. Returns its answer and what it used."""
    session = None
    if request.session_id:
        session = await runner.session_service.get_session(
            app_name=CHAT_APP, user_id=CHAT_USER, session_id=request.session_id)
    if session is None:
        session = await runner.session_service.create_session(app_name=CHAT_APP, user_id=CHAT_USER)

    store = connect_store()
    before = last_audit_id(store)
    message = types.Content(role="user", parts=[types.Part(text=request.message)])
    answer, specialists = "", []
    try:
        async for event in runner.run_async(user_id=CHAT_USER, session_id=session.id, new_message=message):
            specialists += [call.name for call in event.get_function_calls()]
            if event.is_final_response() and event.content and event.content.parts:
                answer = "".join(p.text for p in event.content.parts if p.text and not p.thought)
        tools_used = [{"tool": e["action"], "ok": bool(e["ok"]), "ms": e["duration_ms"]}
                      for e in audit_since(store, before)]
    except Exception as error:          # e.g. Google login expired or the AI service is unavailable
        raise HTTPException(status_code=502, detail=f"The AI service could not answer: {error}")
    finally:
        store.close()
    return {"session_id": session.id, "answer": answer, "specialists": specialists, "tools_used": tools_used}

# ---------------------------------------------------------------------- the dashboard page
# Serve the files in web/ (index.html, styles.css, app.js) at http://127.0.0.1:8001/
# This line must stay LAST, so the /api/... routes above are matched first.
from pathlib import Path  # noqa: E402

from fastapi.staticfiles import StaticFiles  # noqa: E402

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")