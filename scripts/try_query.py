"""try_query.py - run one question through the SQL guard and print the answer."""
from copilot.db import connect_billing_readonly
from copilot.sql_guard import run_safe_query

SQL = """
SELECT c.name,
       MAX(CAST(julianday('2026-10-25') - julianday(o.due_date) AS INTEGER)) AS days
FROM sales_orders o
JOIN customers c ON c.id = o.customer_id
WHERE c.city = 'Sharjah'
  AND o.status = 'delivered'
  AND o.total - o.paid_amount > 0.005
GROUP BY c.id
HAVING days > 60
ORDER BY days DESC
"""

con = connect_billing_readonly()
result = run_safe_query(con, SQL)
print(result["row_count"], "shops")
for row in result["rows"]:
    print(row)
con.close()