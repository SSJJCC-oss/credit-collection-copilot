"""tools.py - the ONLY functions the AI agents are allowed to call.

Each tool:
  * takes simple inputs (text, numbers) that an AI can fill in,
  * opens the databases itself (billing read-only, copilot store read-write),
  * returns a plain dictionary - or {"error": "..."} instead of crashing,
  * is written to the audit log, with how long it took.
There is deliberately NO tool to approve, reject or send a reminder: only a person can do that.
"""
import json
import sqlite3
import time

from copilot import credit_rules, finance, quiet_shops, reminders, sql_guard
from copilot.config import load_settings
from copilot.db import connect_billing_readonly, get_as_of_date
from copilot.store import connect_store, list_drafts as store_list_drafts, log_event, save_order_review


def find_customer(con: sqlite3.Connection, name: str) -> dict:
    """Find one shop by (part of) its name. Raises LookupError if none or several match."""
    wanted = name.strip()
    rows = con.execute("SELECT id, name, city FROM customers WHERE name LIKE ? ORDER BY name",
                       (f"%{wanted}%",)).fetchall()
    exact = [r for r in rows if r["name"].lower() == wanted.lower()]
    if exact:
        return dict(exact[0])
    if len(rows) == 1:
        return dict(rows[0])
    if not rows:
        raise LookupError(f"No shop matches '{name}'.")
    names = ", ".join(r["name"] for r in rows[:10])
    raise LookupError(f"'{name}' matches {len(rows)} shops: {names}. Please use the full name.")


def _run_tool(tool_name: str, arguments: dict, work) -> dict:
    """Open the databases, run one tool, catch expected errors, and write it to the audit log."""
    settings = load_settings()
    billing = connect_billing_readonly()
    store = connect_store()
    started = time.perf_counter()
    try:
        result = work(billing, store, settings, get_as_of_date(billing))
        ok, summary = True, json.dumps(result, default=str)[:300]
    except (ValueError, LookupError, sql_guard.UnsafeQueryError) as error:
        result = {"error": str(error)}
        ok, summary = False, str(error)
    duration_ms = int((time.perf_counter() - started) * 1000)
    log_event(store, "copilot", tool_name, arguments, summary, ok, duration_ms)
    billing.close()
    store.close()
    return result


# ------------------------------------------------------------------------- briefing agent

def get_briefing() -> dict:
    """Today's credit and collections briefing: total owed, overdue amounts by age
    (not_due, 1-30, 31-60, 61-90, 90+ days past the due date), the top 10 shops to chase,
    shops over their credit limit, and post-dated cheques not yet cleared. Amounts are in `currency`."""
    def work(billing, store, settings, as_of):
        b = finance.build_briefing(billing, as_of, settings.currency)
        return {**b, "over_limit_count": len(b["over_limit"]), "over_limit": b["over_limit"][:10]}
    return _run_tool("get_briefing", {}, work)


def find_quiet_shops(limit: int = 10) -> dict:
    """Shops that have stopped ordering compared with their usual rhythm, biggest monthly
    business at risk first. Each has: usual gap between orders, days silent, monthly value at risk."""
    def work(billing, store, settings, as_of):
        quiet = quiet_shops.find_quiet_shops(billing, as_of)
        return {"as_of": as_of, "currency": settings.currency, "total_found": len(quiet), "shops": quiet[:limit]}
    return _run_tool("find_quiet_shops", {"limit": limit}, work)


# --------------------------------------------------------------------------- credit agent

def list_pending_orders() -> dict:
    """Orders waiting for an approval decision (status new or to_confirm), oldest first."""
    def work(billing, store, settings, as_of):
        orders = credit_rules.list_pending_orders(billing)
        return {"as_of": as_of, "currency": settings.currency, "count": len(orders), "orders": orders}
    return _run_tool("list_pending_orders", {}, work)


def review_order(order_no: str) -> dict:
    """Recommend APPROVE, REVIEW or HOLD for one waiting order (e.g. 'SO-026777'), with every
    reason and the numbers behind it. The decision comes from fixed credit rules; explain it, never change it."""
    def work(billing, store, settings, as_of):
        result = credit_rules.review_order(billing, order_no.strip().upper(), as_of)
        save_order_review(store, result, as_of, credit_rules.RULES_VERSION)
        return {**result, "as_of": as_of, "currency": settings.currency,
                "rules_version": credit_rules.RULES_VERSION}
    return _run_tool("review_order", {"order_no": order_no}, work)


def get_customer_overview(customer_name: str) -> dict:
    """One shop's credit picture: credit limit and days, money owed and overdue, worst overdue bill,
    usual order size, average days late paying, and whether it has gone quiet."""
    def work(billing, store, settings, as_of):
        shop = find_customer(billing, customer_name)
        row = billing.execute("SELECT credit_limit, credit_days, customer_type FROM customers WHERE id = ?",
                              (shop["id"],)).fetchone()
        invoices = [i for i in finance.get_open_invoices(billing, as_of) if i["customer_id"] == shop["id"]]
        card = finance.summarise_by_customer(invoices).get(shop["id"], {})
        history = quiet_shops.get_order_history(billing).get(shop["id"])
        quiet = quiet_shops.check_shop(history, as_of) if history else None
        avg_late = billing.execute("""
            SELECT AVG(julianday(p.payment_date) - julianday(o.due_date))
            FROM payments p JOIN sales_orders o ON o.id = p.order_id
            WHERE p.customer_id = ? AND p.payment_date >= date(?, '-365 day')""",
            (shop["id"], as_of)).fetchone()[0]
        return {
            "as_of": as_of, "currency": settings.currency,
            "customer_id": shop["id"], "customer_name": shop["name"], "city": shop["city"],
            "customer_type": row["customer_type"],
            "credit_limit": row["credit_limit"], "credit_days": row["credit_days"],
            "owed": card.get("owed", 0.0), "overdue": card.get("overdue", 0.0),
            "worst_days_overdue": card.get("worst_days_overdue", 0),
            "unpaid_invoices": card.get("invoices", 0),
            "avg_days_late_last_year": round(avg_late, 1) if avg_late is not None else None,
            "usual_gap_between_orders_days": quiet["usual_gap_days"] if quiet else None,
            "days_since_last_order": quiet["days_silent"] if quiet else None,
            "has_gone_quiet": quiet["is_quiet"] if quiet else False,
        }
    return _run_tool("get_customer_overview", {"customer_name": customer_name}, work)


# ---------------------------------------------------------------------- collections agent

def get_overdue_invoices(customer_name: str) -> dict:
    """One shop's unpaid invoices that are past their due date (invoice number, due date,
    balance, days overdue), oldest first."""
    def work(billing, store, settings, as_of):
        shop = find_customer(billing, customer_name)
        invoices = reminders.get_overdue_invoices(billing, shop["id"], as_of)
        return {"as_of": as_of, "currency": settings.currency, "customer_name": shop["name"],
                "count": len(invoices), "total_overdue": round(sum(i["balance"] for i in invoices), 2),
                "invoices": [{k: i[k] for k in ("order_no", "due_date", "balance", "days_overdue")}
                             for i in invoices]}
    return _run_tool("get_overdue_invoices", {"customer_name": customer_name}, work)


def draft_reminder(customer_name: str, language: str = "") -> dict:
    """Write a payment reminder for one shop from its real overdue invoices and put it in the
    approval queue as a DRAFT. It is NOT sent: a person must approve it in the dashboard.
    language: 'en' or 'ar'; leave empty to use the shop's preferred language."""
    def work(billing, store, settings, as_of):
        shop = find_customer(billing, customer_name)
        return reminders.draft_reminder(billing, store, shop["id"], as_of, settings.currency,
                                        language.strip().lower() or None)
    return _run_tool("draft_reminder", {"customer_name": customer_name, "language": language}, work)


def list_drafts(status: str = "draft") -> dict:
    """Reminder drafts in the approval queue. status: 'draft' (waiting for a person),
    'logged', 'approved', 'rejected', or 'all'."""
    def work(billing, store, settings, as_of):
        drafts = store_list_drafts(store, None if status == "all" else status)
        return {"status": status, "count": len(drafts),
                "drafts": [{k: d[k] for k in ("id", "customer_name", "language", "channel",
                                              "amount_due", "status", "subject", "created_at")}
                           for d in drafts]}
    return _run_tool("list_drafts", {"status": status}, work)


# ------------------------------------------------------------------------- data Q&A agent

def describe_schema() -> dict:
    """The database tables and columns you may query, with a few facts about how the data works."""
    def work(billing, store, settings, as_of):
        return {"tables": sql_guard.describe_schema(), "as_of_date": as_of, "currency": settings.currency,
                "notes": ["A delivered order is the invoice; money owed = total - paid_amount on delivered orders.",
                          "Days overdue = as_of_date minus due_date (use julianday()).",
                          "Order statuses: new, to_confirm (waiting), confirmed, delivered, cancelled.",
                          "Only customers with status 'confirmed' are active shops."]}
    return _run_tool("describe_schema", {}, work)


def run_safe_query(sql: str) -> dict:
    """Run ONE read-only SELECT on the allowed tables (see describe_schema). At most 200 rows
    are returned; 'truncated' is true if there were more. Refused queries return an error explaining why."""
    def work(billing, store, settings, as_of):
        return sql_guard.run_safe_query(billing, sql, settings.max_query_rows)
    return _run_tool("run_safe_query", {"sql": sql}, work)