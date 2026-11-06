"""Tests for copilot/sql_guard.py - the safety rules for "Ask your data". No API key needed."""
import pytest

from copilot.db import connect_billing_readonly
from copilot.sql_guard import UnsafeQueryError, check_sql_text, describe_schema, run_safe_query


@pytest.fixture
def con():
    """A fresh read-only connection for each test, closed afterwards."""
    connection = connect_billing_readonly()
    yield connection
    connection.close()


# ---- Things that must be ALLOWED --------------------------------------------------------

def test_simple_select_works(con):
    result = run_safe_query(con, "SELECT name, city FROM customers WHERE city = 'Sharjah'")
    assert result["columns"] == ["name", "city"]
    assert result["row_count"] == 47
    assert all(row[1] == "Sharjah" for row in result["rows"])


def test_joins_aggregates_and_with_are_allowed(con):
    sql = """WITH totals AS (
                 SELECT customer_id, SUM(total) AS sales FROM sales_orders GROUP BY customer_id)
             SELECT c.name, t.sales FROM totals t JOIN customers c ON c.id = t.customer_id
             ORDER BY t.sales DESC LIMIT 3;"""
    assert run_safe_query(con, sql)["row_count"] == 3


def test_row_limit_is_enforced(con):
    result = run_safe_query(con, "SELECT id FROM sales_orders", max_rows=50)
    assert result["row_count"] == 50
    assert result["truncated"] is True


# ---- Things that must be REFUSED --------------------------------------------------------

@pytest.mark.parametrize("sql", [
    "DELETE FROM customers",
    "UPDATE customers SET credit_limit = 999999",
    "DROP TABLE customers",
    "INSERT INTO users (name) VALUES ('hacker')",
    "PRAGMA table_info(customers)",
    "ATTACH DATABASE 'other.db' AS other",
])
def test_anything_but_select_is_refused(con, sql):
    with pytest.raises(UnsafeQueryError):
        run_safe_query(con, sql)


def test_two_statements_are_refused():
    with pytest.raises(UnsafeQueryError, match="one statement"):
        check_sql_text("SELECT 1; DELETE FROM customers")


def test_answer_key_table_is_refused(con):
    with pytest.raises(UnsafeQueryError, match="synthetic_notes"):
        run_safe_query(con, "SELECT * FROM synthetic_notes")


def test_private_columns_are_refused(con):
    with pytest.raises(UnsafeQueryError, match="customers.email"):
        run_safe_query(con, "SELECT name, email FROM customers")


def test_select_star_on_table_with_private_columns_is_refused(con):
    with pytest.raises(UnsafeQueryError):
        run_safe_query(con, "SELECT * FROM customers")


def test_hidden_table_in_subquery_is_refused(con):
    with pytest.raises(UnsafeQueryError, match="synthetic_notes"):
        run_safe_query(con, "SELECT name FROM customers WHERE id IN (SELECT ref_id FROM synthetic_notes)")


def test_views_are_refused(con):
    with pytest.raises(UnsafeQueryError):
        run_safe_query(con, "SELECT * FROM v_outstanding_orders")


def test_guard_is_removed_after_each_query(con):
    with pytest.raises(UnsafeQueryError):
        run_safe_query(con, "SELECT * FROM synthetic_notes")
    # Normal code using the same connection must not be affected by the guard.
    assert con.execute("SELECT COUNT(*) FROM synthetic_notes").fetchone()[0] == 334


def test_schema_description_hides_private_things():
    schema = describe_schema()
    assert "synthetic_notes" not in schema
    assert "email" not in schema["customers"]
    assert "name" in schema["customers"]