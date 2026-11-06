"""quiet_shops.py - find shops whose ordering has stopped compared with their usual rhythm. No AI."""
import sqlite3
from datetime import date
from statistics import median

QUIET_MULTIPLIER = 4      # silent for more than 4x the usual gap between orders...
QUIET_MIN_DAYS = 45       # ...and for at least 45 days
MIN_ORDERS = 5            # need at least 5 orders to know a shop's rhythm
RECENT_ORDERS = 20        # rhythm is measured on the shop's last 20 orders


def get_order_history(con: sqlite3.Connection) -> dict[int, dict]:
    """Every confirmed shop's non-cancelled order dates and totals, oldest first."""
    rows = con.execute("""
        SELECT c.id AS customer_id, c.name AS customer_name, c.city, o.order_date, o.total
        FROM sales_orders o JOIN customers c ON c.id = o.customer_id
        WHERE c.status = 'confirmed' AND o.status != 'cancelled'
        ORDER BY c.id, o.order_date""").fetchall()
    history = {}
    for r in rows:
        cid = r["customer_id"]
        if cid not in history:
            history[cid] = {"customer_id": cid, "customer_name": r["customer_name"], "city": r["city"],
                            "dates": [], "totals": []}
        history[cid]["dates"].append(r["order_date"])
        history[cid]["totals"].append(r["total"])
    return history


def usual_gap_days(dates: list[str]) -> float | None:
    """Median number of days between a shop's recent orders, or None if too few orders."""
    if len(dates) < MIN_ORDERS:
        return None
    recent = [date.fromisoformat(d) for d in dates[-RECENT_ORDERS:]]
    gaps = [(later - earlier).days for earlier, later in zip(recent, recent[1:])]
    return max(median(gaps), 1)


def check_shop(shop: dict, as_of: str) -> dict | None:
    """Compare days since the last order with the usual gap. Returns the details, or None if no rhythm."""
    gap = usual_gap_days(shop["dates"])
    if gap is None:
        return None
    last_order = shop["dates"][-1]
    days_silent = (date.fromisoformat(as_of) - date.fromisoformat(last_order)).days
    recent_totals = shop["totals"][-RECENT_ORDERS:]
    avg_order = sum(recent_totals) / len(recent_totals)
    return {
        "customer_id": shop["customer_id"],
        "customer_name": shop["customer_name"],
        "city": shop["city"],
        "last_order": last_order,
        "days_silent": days_silent,
        "usual_gap_days": gap,
        "times_usual": round(days_silent / gap, 1),
        "monthly_value": round(avg_order * 30 / gap, 2),
        "is_quiet": days_silent > QUIET_MULTIPLIER * gap and days_silent >= QUIET_MIN_DAYS,
    }


def find_quiet_shops(con: sqlite3.Connection, as_of: str) -> list[dict]:
    """Shops that have gone quiet, biggest monthly business at risk first."""
    quiet = []
    for shop in get_order_history(con).values():
        result = check_shop(shop, as_of)
        if result and result["is_quiet"]:
            quiet.append(result)
    quiet.sort(key=lambda s: s["monthly_value"], reverse=True)
    return quiet