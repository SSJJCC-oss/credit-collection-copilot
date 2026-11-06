"""credit_rules.py - APPROVE / HOLD / REVIEW for orders waiting for approval. Plain rules, no AI."""
import sqlite3

HOLD_OVERDUE_DAYS = 90          # any bill later than this -> HOLD
REVIEW_OVERDUE_DAYS = 60        # any bill later than this (but not 90+) -> REVIEW
REVIEW_SIZE_MULTIPLIER = 2.0    # order bigger than 2x the usual order -> REVIEW
REVIEW_AVG_LATE_DAYS = 45       # pays on average more than 45 days late -> REVIEW

STRENGTH = {"APPROVE": 0, "REVIEW": 1, "HOLD": 2}


def list_pending_orders(con: sqlite3.Connection) -> list[dict]:
    """Orders waiting for a decision (status new or to_confirm), oldest first."""
    rows = con.execute("""
        SELECT o.order_no, o.order_date, o.status, o.total, c.id AS customer_id, c.name AS customer_name, c.city
        FROM sales_orders o JOIN customers c ON c.id = o.customer_id
        WHERE o.status IN ('new', 'to_confirm')
        ORDER BY o.order_date, o.id""").fetchall()
    return [dict(r) for r in rows]


def get_order_facts(con: sqlite3.Connection, order_no: str, as_of: str) -> dict:
    """Everything the rules need to judge one order: the order, the shop's limit, debts and habits."""
    order = con.execute("""
        SELECT o.order_no, o.total, o.status, c.id AS customer_id, c.name AS customer_name,
               c.credit_limit, c.credit_days
        FROM sales_orders o JOIN customers c ON c.id = o.customer_id
        WHERE o.order_no = ?""", (order_no,)).fetchone()
    if order is None:
        raise ValueError(f"Order {order_no} not found")
    facts = dict(order)
    cid = facts["customer_id"]

    debts = con.execute("""
        SELECT COALESCE(SUM(total - paid_amount), 0) AS owed,
               COALESCE(MAX(CAST(julianday(?) - julianday(due_date) AS INTEGER)), 0) AS worst_days_overdue
        FROM sales_orders
        WHERE customer_id = ? AND status = 'delivered' AND total - paid_amount > 0.005""",
        (as_of, cid)).fetchone()
    facts["owed"] = round(debts["owed"], 2)
    facts["worst_days_overdue"] = debts["worst_days_overdue"]

    facts["usual_order"] = con.execute("""
        SELECT AVG(total) FROM sales_orders
        WHERE customer_id = ? AND status = 'delivered' AND order_date >= date(?, '-365 day')""",
        (cid, as_of)).fetchone()[0]

    facts["avg_days_late"] = con.execute("""
        SELECT AVG(julianday(p.payment_date) - julianday(o.due_date))
        FROM payments p JOIN sales_orders o ON o.id = p.order_id
        WHERE p.customer_id = ? AND p.payment_date >= date(?, '-365 day')""",
        (cid, as_of)).fetchone()[0]

    facts["headroom"] = round(facts["credit_limit"] - facts["owed"], 2)
    return facts


def decide(facts: dict) -> dict:
    """Apply the rules to one order's facts. Returns the decision and every reason that fired."""
    reasons = []

    if facts["owed"] + facts["total"] > facts["credit_limit"]:
        reasons.append({"rule": "credit_limit", "result": "HOLD",
                        "detail": f"Owes {facts['owed']:,.2f}; with this order ({facts['total']:,.2f}) "
                                  f"that exceeds the credit limit of {facts['credit_limit']:,.2f}."})

    worst = facts["worst_days_overdue"]
    if worst > HOLD_OVERDUE_DAYS:
        reasons.append({"rule": "overdue", "result": "HOLD",
                        "detail": f"Oldest unpaid bill is {worst} days overdue (limit {HOLD_OVERDUE_DAYS})."})
    elif worst > REVIEW_OVERDUE_DAYS:
        reasons.append({"rule": "overdue", "result": "REVIEW",
                        "detail": f"Oldest unpaid bill is {worst} days overdue."})

    usual = facts["usual_order"]
    if usual and facts["total"] > REVIEW_SIZE_MULTIPLIER * usual:
        reasons.append({"rule": "order_size", "result": "REVIEW",
                        "detail": f"This order ({facts['total']:,.2f}) is {facts['total'] / usual:.1f}x "
                                  f"the usual order ({usual:,.2f})."})

    late = facts["avg_days_late"]
    if late is not None and late > REVIEW_AVG_LATE_DAYS:
        reasons.append({"rule": "payment_history", "result": "REVIEW",
                        "detail": f"Over the last year, pays on average {late:.0f} days after the due date."})

    if reasons:
        decision = max((r["result"] for r in reasons), key=lambda d: STRENGTH[d])
    else:
        decision = "APPROVE"
        reasons.append({"rule": "all_clear", "result": "APPROVE",
                        "detail": f"Within credit limit (headroom {facts['headroom']:,.2f}), nothing seriously "
                                  f"overdue, normal order size."})
    return {"decision": decision, "reasons": reasons}


def review_order(con: sqlite3.Connection, order_no: str, as_of: str) -> dict:
    """Judge one waiting order: its facts plus the decision and reasons."""
    facts = get_order_facts(con, order_no, as_of)
    return {**facts, **decide(facts)}