"""sql_guard.py - run ONE read-only SELECT on allow-listed tables and columns, with a row limit.

Two layers of protection:
  1. Text checks before the query runs (one statement, must be a SELECT, not too long).
  2. SQLite's own "authorizer": the database asks us about every table, column and
     action while preparing the query, and we refuse anything not on the allow-list.
The connection itself is also read-only (see db.py), so writes are impossible anyway.
"""
import sqlite3

# Tables and columns the "Ask your data" feature may read.
# Not listed (so always refused): synthetic_notes (test answer key), the views,
# customers.phone / customers.email and users.email (personal contact details).
ALLOWED_COLUMNS = {
    "customers": {"id", "code", "name", "customer_type", "contact_person", "city",
                  "credit_limit", "credit_days", "status", "home_warehouse_id", "created_at"},
    "sales_orders": {"id", "order_no", "customer_id", "warehouse_id", "order_date", "due_date",
                     "status", "subtotal", "tax_amount", "total", "paid_amount", "created_by"},
    "sales_order_lines": {"id", "order_id", "item_id", "quantity", "unit_price", "line_total"},
    "payments": {"id", "customer_id", "order_id", "payment_date", "amount", "method"},
    "items": {"id", "sku", "name", "category", "unit", "cost_price", "sale_price",
              "reorder_level", "supplier_id", "active"},
    "stock": {"warehouse_id", "item_id", "quantity"},
    "warehouses": {"id", "name", "city", "is_main"},
    "users": {"id", "name", "role", "active"},
    "suppliers": {"id", "name", "city"},
    "ext_customer_profile": {"customer_id", "trn", "preferred_language", "main_rep_id"},
    "ext_cheque_details": {"payment_id", "cheque_no", "cheque_date", "bank", "status"},
}
MAX_SQL_LENGTH = 2000


class UnsafeQueryError(Exception):
    """Raised when a query breaks a safety rule. The message says which rule and why."""


def check_sql_text(sql: str) -> str:
    """Text-level checks. Returns the cleaned query or raises UnsafeQueryError."""
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        raise UnsafeQueryError("The query is empty.")
    if len(cleaned) > MAX_SQL_LENGTH:
        raise UnsafeQueryError(f"The query is longer than {MAX_SQL_LENGTH} characters.")
    if ";" in cleaned:
        raise UnsafeQueryError("Only one statement is allowed (found a ';' in the middle).")
    first_word = cleaned.split()[0].upper()
    if first_word not in ("SELECT", "WITH"):
        raise UnsafeQueryError(f"Only SELECT queries are allowed, not {first_word}.")
    return cleaned


def make_authorizer(refusals: list[str]):
    """Build the callback SQLite calls for every action while preparing a query."""
    def authorizer(action, arg1, arg2, db_name, trigger):
        if action == sqlite3.SQLITE_SELECT:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_FUNCTION:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_READ:
            table, column = arg1, arg2
            if table not in ALLOWED_COLUMNS:
                refusals.append(f"table '{table}' is not available")
                return sqlite3.SQLITE_DENY
            if column and column not in ALLOWED_COLUMNS[table]:
                refusals.append(f"column '{table}.{column}' is not available")
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        refusals.append("only reading data is allowed")
        return sqlite3.SQLITE_DENY
    return authorizer


def run_safe_query(con: sqlite3.Connection, sql: str, max_rows: int = 200) -> dict:
    """Run one checked SELECT. Returns columns, rows (at most max_rows) and whether it was cut short."""
    cleaned = check_sql_text(sql)
    refusals = []
    con.set_authorizer(make_authorizer(refusals))
    try:
        cursor = con.execute(cleaned)
        rows = cursor.fetchmany(max_rows + 1)
    except sqlite3.DatabaseError as error:
        if refusals:
            raise UnsafeQueryError("Query refused: " + "; ".join(sorted(set(refusals)))) from error
        raise UnsafeQueryError(f"The query could not run: {error}") from error
    finally:
        con.set_authorizer(None)
    columns = [d[0] for d in cursor.description]
    return {
        "columns": columns,
        "rows": [list(r) for r in rows[:max_rows]],
        "row_count": min(len(rows), max_rows),
        "truncated": len(rows) > max_rows,
    }


def describe_schema() -> dict[str, list[str]]:
    """The tables and columns the AI is allowed to query (what it 'sees' of the database)."""
    return {table: sorted(columns) for table, columns in ALLOWED_COLUMNS.items()}