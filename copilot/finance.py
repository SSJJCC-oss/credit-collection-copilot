"""finance.py - the money maths: what is owed, how overdue, and who to chase. No AI."""
import sqlite3

BUCKETS = ["not_due", "1-30", "31-60", "61-90", "90+"]
BUCKET_WEIGHTS = {"not_due": 0, "1-30": 1, "31-60": 2, "61-90": 3, "90+": 4}


def age_bucket(days_overdue: int) -> str:
    """Which ageing bucket a bill falls into, by days past its due date."""
    if days_overdue <= 0:
        return "not_due"
    if days_overdue <= 30:
        return "1-30"
    if days_overdue <= 60:
        return "31-60"
    if days_overdue <= 90:
        return "61-90"
    return "90+"


def get_open_invoices(con: sqlite3.Connection, as_of: str) -> list[dict]:
    """Every delivered order that still has money owed, with days overdue as of `as_of`."""
    rows = con.execute("""
        SELECT o.id AS order_id, o.order_no, o.customer_id, c.name AS customer_name, c.city,
               o.order_date, o.due_date, o.total, o.paid_amount,
               ROUND(o.total - o.paid_amount, 2) AS balance,
               CAST(julianday(?) - julianday(o.due_date) AS INTEGER) AS days_overdue
        FROM sales_orders o
        JOIN customers c ON c.id = o.customer_id
        WHERE o.status = 'delivered' AND o.total - o.paid_amount > 0.005
        ORDER BY o.due_date""", (as_of,)).fetchall()
    invoices = [dict(r) for r in rows]
    for inv in invoices:
        inv["bucket"] = age_bucket(inv["days_overdue"])
    return invoices


def ageing_summary(invoices: list[dict]) -> dict[str, dict]:
    """Total balance and number of invoices in each ageing bucket."""
    summary = {b: {"amount": 0.0, "invoices": 0} for b in BUCKETS}
    for inv in invoices:
        summary[inv["bucket"]]["amount"] += inv["balance"]
        summary[inv["bucket"]]["invoices"] += 1
    for b in BUCKETS:
        summary[b]["amount"] = round(summary[b]["amount"], 2)
    return summary

def summarise_by_customer(invoices: list[dict]) -> dict[int, dict]:
    """Group unpaid bills by shop: total owed, amount overdue, worst lateness and a chase priority."""
    shops = {}
    for inv in invoices:
        cid = inv["customer_id"]
        if cid not in shops:
            shops[cid] = {"customer_id": cid, "customer_name": inv["customer_name"], "city": inv["city"],
                          "owed": 0.0, "overdue": 0.0, "worst_days_overdue": 0, "invoices": 0, "priority": 0.0}
        s = shops[cid]
        s["owed"] += inv["balance"]
        s["invoices"] += 1
        if inv["days_overdue"] > 0:
            s["overdue"] += inv["balance"]
        s["worst_days_overdue"] = max(s["worst_days_overdue"], inv["days_overdue"])
        s["priority"] += inv["balance"] * BUCKET_WEIGHTS[inv["bucket"]]
    for s in shops.values():
        for key in ("owed", "overdue", "priority"):
            s[key] = round(s[key], 2)
    return shops


def top_to_chase(by_customer: dict[int, dict], n: int = 10) -> list[dict]:
    """The n shops to chase first: highest priority (overdue money, weighted by lateness)."""
    overdue_shops = [s for s in by_customer.values() if s["overdue"] > 0]
    overdue_shops.sort(key=lambda s: s["priority"], reverse=True)
    return overdue_shops[:n]


def get_credit_limits(con: sqlite3.Connection) -> dict[int, float]:
    """Credit limit of every confirmed shop: {customer_id: limit}."""
    rows = con.execute("SELECT id, credit_limit FROM customers WHERE status = 'confirmed'").fetchall()
    return {r["id"]: r["credit_limit"] for r in rows}


def over_limit_customers(by_customer: dict[int, dict], limits: dict[int, float]) -> list[dict]:
    """Shops that owe more than their credit limit, biggest excess first."""
    result = []
    for cid, s in by_customer.items():
        limit = limits.get(cid)
        if limit is not None and s["owed"] > limit:
            result.append({**s, "credit_limit": limit, "excess": round(s["owed"] - limit, 2)})
    result.sort(key=lambda s: s["excess"], reverse=True)
    return result


def get_pending_cheques(con: sqlite3.Connection, as_of: str) -> dict:
    """Post-dated cheques received but not yet cleared (cheque date after `as_of`)."""
    row = con.execute("""
        SELECT COUNT(*) AS cheques, COALESCE(ROUND(SUM(p.amount), 2), 0) AS amount
        FROM ext_cheque_details d JOIN payments p ON p.id = d.payment_id
        WHERE d.cheque_date > ?""", (as_of,)).fetchone()
    return dict(row)


def build_briefing(con: sqlite3.Connection, as_of: str, currency: str = "AED", top_n: int = 10) -> dict:
    """All the numbers for the daily credit & collections briefing, in one dictionary."""
    invoices = get_open_invoices(con, as_of)
    ageing = ageing_summary(invoices)
    by_customer = summarise_by_customer(invoices)
    total_owed = round(sum(b["amount"] for b in ageing.values()), 2)
    return {
        "as_of": as_of,
        "currency": currency,
        "total_owed": total_owed,
        "total_overdue": round(total_owed - ageing["not_due"]["amount"], 2),
        "ageing": ageing,
        "top_to_chase": top_to_chase(by_customer, top_n),
        "over_limit": over_limit_customers(by_customer, get_credit_limits(con)),
        "pending_cheques": get_pending_cheques(con, as_of),
    }