"""
inspect_db.py - Step 1 of BillCRM Copilot: profile the BillCRM demo database.

What it does
------------
Opens the SQLite file READ-ONLY (it cannot change the file even by accident),
then writes a Markdown report listing every table, its columns, row counts,
sample rows, data-quality checks and the key business numbers the copilot
will care about (outstanding, ageing, credit limits, order queue).

Run (Windows, from the project folder, venv active):
    python scripts\\inspect_db.py data\\crm_demo.db --out docs\\DATA_PROFILE.md

Only the Python standard library is used, so no pip install is needed yet.
"""

import argparse
import sqlite3
from pathlib import Path


def open_readonly(db_path: Path) -> sqlite3.Connection:
    # "mode=ro" in a URI tells SQLite to refuse every write. Path.as_uri()
    # builds a correct file:///C:/... URI on Windows and file:///... on Linux.
    uri = db_path.resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def md_table(headers, rows) -> str:
    """Turn a list of tuples into a Markdown table (for readable reports)."""
    out = ["| " + " | ".join(map(str, headers)) + " |",
           "|" + "---|" * len(headers)]
    for r in rows:
        out.append("| " + " | ".join("" if v is None else str(v) for v in r) + " |")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("db", type=Path, help="path to crm_demo.db")
    ap.add_argument("--out", type=Path, default=Path("docs/DATA_PROFILE.md"))
    args = ap.parse_args()

    con = open_readonly(args.db)
    q = lambda sql: con.execute(sql).fetchall()          # tiny helper
    one = lambda sql: con.execute(sql).fetchone()[0]     # single value
    rep = [f"# Data profile: `{args.db.name}`\n"]

    # ---- 1. Structure: every table, its columns, row count, 3 sample rows
    tables = [r[0] for r in q("SELECT name FROM sqlite_master "
                              "WHERE type='table' ORDER BY name")]
    rep.append("## 1. Tables\n")
    rep.append(md_table(["table", "rows"],
                        [(t, one(f'SELECT COUNT(*) FROM "{t}"')) for t in tables]))
    for t in tables:
        cols = q(f'PRAGMA table_info("{t}")')  # (cid, name, type, notnull, default, pk)
        names = [c[1] for c in cols]
        rep.append(f"\n### {t}\n")
        rep.append("Columns: " + ", ".join(
            f"`{c[1]}` {c[2]}{' (PK)' if c[5] else ''}" for c in cols))
        rep.append("\n" + md_table(names, q(f'SELECT * FROM "{t}" LIMIT 3')))

    # Views are saved queries the original developers wrote - useful hints
    rep.append("\n## 2. Views (saved queries)\n")
    for name, sql in q("SELECT name, sql FROM sqlite_master WHERE type='view'"):
        rep.append(f"**{name}**\n```sql\n{sql}\n```")

    # ---- 2. Relationships. The schema declares NO foreign keys, so we infer
    # them from column names and then PROVE each one by counting orphans.
    links = [("sales_orders.customer_id", "customers.id"),
             ("sales_orders.warehouse_id", "warehouses.id"),
             ("sales_orders.created_by", "users.id"),
             ("sales_order_lines.order_id", "sales_orders.id"),
             ("sales_order_lines.item_id", "items.id"),
             ("payments.order_id", "sales_orders.id"),
             ("payments.customer_id", "customers.id"),
             ("customers.home_warehouse_id", "warehouses.id"),
             ("items.supplier_id", "suppliers.id"),
             ("purchase_orders.supplier_id", "suppliers.id"),
             ("purchase_lines.po_id", "purchase_orders.id"),
             ("purchase_lines.item_id", "items.id"),
             ("stock.item_id", "items.id"),
             ("stock.warehouse_id", "warehouses.id"),
             ("expenses.warehouse_id", "warehouses.id")]
    rows = []
    for child, parent in links:
        ct, cc = child.split(".")
        pt, pc = parent.split(".")
        orphans = one(f"SELECT COUNT(*) FROM {ct} c LEFT JOIN {pt} p "
                      f"ON p.{pc}=c.{cc} WHERE p.{pc} IS NULL")
        rows.append((child, parent, orphans))
    rep.append("\n## 3. Inferred relationships (orphan rows should be 0)\n")
    rep.append(md_table(["child column", "parent", "orphans"], rows))

    # ---- 3. Data-quality checks: do the money columns add up?
    checks = {
        "line_total = quantity x unit_price":
            "SELECT COUNT(*) FROM sales_order_lines "
            "WHERE ABS(line_total-quantity*unit_price)>0.02",
        "order subtotal = sum of its lines":
            "SELECT COUNT(*) FROM (SELECT o.subtotal s, SUM(l.line_total) t "
            "FROM sales_orders o JOIN sales_order_lines l ON l.order_id=o.id "
            "GROUP BY o.id) WHERE ABS(s-t)>0.02",
        "tax_amount = 5% of subtotal (UAE VAT)":
            "SELECT COUNT(*) FROM sales_orders "
            "WHERE ABS(tax_amount-ROUND(subtotal*0.05,2))>0.02",
        "total = subtotal + tax":
            "SELECT COUNT(*) FROM sales_orders "
            "WHERE ABS(total-subtotal-tax_amount)>0.02",
        "paid_amount = sum of payments":
            "SELECT COUNT(*) FROM (SELECT o.paid_amount p, "
            "COALESCE(SUM(y.amount),0) s FROM sales_orders o LEFT JOIN payments y "
            "ON y.order_id=o.id GROUP BY o.id) WHERE ABS(p-s)>0.02",
        "due_date = order_date + customer credit_days":
            "SELECT COUNT(*) FROM sales_orders o JOIN customers c "
            "ON c.id=o.customer_id WHERE julianday(o.due_date)-"
            "julianday(o.order_date) <> c.credit_days",
        "payment before order date":
            "SELECT COUNT(*) FROM payments y JOIN sales_orders o "
            "ON o.id=y.order_id WHERE y.payment_date < o.order_date",
        "customers with no email": "SELECT COUNT(*) FROM customers WHERE email IS NULL",
        "customers with no phone": "SELECT COUNT(*) FROM customers WHERE phone IS NULL",
    }
    rep.append("\n## 4. Data-quality checks (rows failing)\n")
    rep.append(md_table(["check", "failing rows"],
                        [(k, one(v)) for k, v in checks.items()]))

    # ---- 4. Business snapshot. "As of" = the latest date found in the data,
    # because the demo data stops before today's date (see ASSUMPTIONS.md).
    as_of = one("SELECT MAX(d) FROM (SELECT MAX(order_date) d FROM sales_orders "
                "UNION SELECT MAX(payment_date) FROM payments)")
    rep.append(f"\n## 5. Business snapshot (as of {as_of})\n")
    rep.append("Order status counts:\n")
    rep.append(md_table(["status", "orders", "first", "last", "total AED", "paid AED"],
                        q("SELECT status, COUNT(*), MIN(order_date), MAX(order_date), "
                          "ROUND(SUM(total)), ROUND(SUM(paid_amount)) "
                          "FROM sales_orders GROUP BY status")))

    # Ageing: days past the due date, for delivered orders with a balance left
    rep.append("\nOutstanding on delivered orders, aged by days past due date:\n")
    rep.append(md_table(["bucket", "invoices", "balance AED"], q(f"""
        SELECT CASE WHEN d<=0 THEN '0 not yet due' WHEN d<=30 THEN '1-30'
                    WHEN d<=60 THEN '31-60' WHEN d<=90 THEN '61-90' ELSE '90+' END,
               COUNT(*), ROUND(SUM(bal))
        FROM (SELECT julianday('{as_of}')-julianday(due_date) d,
                     total-paid_amount bal
              FROM sales_orders
              WHERE status='delivered' AND total-paid_amount>0.005)
        GROUP BY 1 ORDER BY 1""")))

    rep.append("\nCustomers whose unpaid balance is above their credit limit:\n")
    rep.append(md_table(["id", "name", "city", "limit", "days", "open balance"], q("""
        WITH b AS (SELECT customer_id, SUM(total-paid_amount) bal
                   FROM sales_orders WHERE status='delivered' GROUP BY 1)
        SELECT c.id, c.name, c.city, c.credit_limit, c.credit_days, ROUND(b.bal)
        FROM b JOIN customers c ON c.id=b.customer_id
        WHERE b.bal > c.credit_limit ORDER BY b.bal-c.credit_limit DESC""")))

    rep.append("\nHow late customers historically pay (payment date vs due date):\n")
    rep.append(md_table(["lateness", "payments"], q("""
        SELECT CASE WHEN l<=0 THEN '0 on time' WHEN l<=30 THEN '1-30 late'
                    WHEN l<=60 THEN '31-60 late' WHEN l<=90 THEN '61-90 late'
                    ELSE '90+ late' END, COUNT(*)
        FROM (SELECT julianday(y.payment_date)-julianday(o.due_date) l
              FROM payments y JOIN sales_orders o ON o.id=y.order_id)
        GROUP BY 1 ORDER BY 1""")))

    rep.append("\nOrders waiting for a decision (status new / to_confirm):\n")
    rep.append(md_table(["id", "order_no", "customer_id", "date", "total", "status"],
                        q("SELECT id, order_no, customer_id, order_date, total, status "
                          "FROM sales_orders WHERE status IN ('new','to_confirm')")))

    rep.append("\nLabels in `synthetic_notes` (answer key left by the data generator):\n")
    rep.append(md_table(["kind", "table", "rows"],
                        q("SELECT kind, ref_table, COUNT(*) FROM synthetic_notes "
                          "GROUP BY 1, 2")))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(rep), encoding="utf-8")
    print(f"Wrote {args.out}  (data as of {as_of}, {len(tables)} tables)")


if __name__ == "__main__":
    main()
