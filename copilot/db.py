"""db.py - opening the billing database safely, and finding the copilot's 'today'."""
import sqlite3
from pathlib import Path

from copilot.config import load_settings


def connect_billing_readonly(path: Path | None = None) -> sqlite3.Connection:
    """Open the billing database READ-ONLY. Any attempt to change it raises an error."""
    path = path or load_settings().billing_db
    if not path.exists():
        raise FileNotFoundError(f"Billing database not found: {path}. Run scripts/seed_demo.py first.")
    con = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def get_as_of_date(con: sqlite3.Connection) -> str:
    """The copilot's 'today': AS_OF_DATE from .env if set, otherwise the latest date in the data."""
    configured = load_settings().as_of_date
    if configured:
        return configured
    return con.execute(
        "SELECT MAX(d) FROM ("
        " SELECT MAX(order_date) AS d FROM sales_orders"
        " UNION SELECT MAX(payment_date) FROM payments)"
    ).fetchone()[0]