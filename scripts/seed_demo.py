"""seed_demo.py - Phase 1: build the copilot demo database from a COPY of the original."""
import shutil
import sqlite3
from pathlib import Path
import random
from datetime import date, timedelta

SOURCE = Path("data/crm_demo.db")            # the original, never modified
TARGET = Path("data/crm_copilot_demo.db")    # the copy we add demo data to
VAT_RATE = 0.05   # UAE VAT is 5%
UAE_BANKS = ["Emirates NBD", "First Abu Dhabi Bank", "Abu Dhabi Commercial Bank", "Dubai Islamic Bank",
             "Mashreq", "RAKBANK", "Commercial Bank of Dubai", "Sharjah Islamic Bank"]


def make_copy(source: Path, target: Path) -> None:
    # TODO 1: if source doesn't exist, stop with an error
    if not source.exists():
        raise FileNotFoundError(f"Original database not found: {source}")

    # TODO 2: if source and target are the same file, stop with an error
    if source.resolve() == target.resolve():
        raise ValueError("Source and target are the same file - refusing to overwrite the original")

    # TODO 3: if target already exists, delete it
    target.unlink(missing_ok=True)

    # TODO 4: copy source to target
    shutil.copyfile(source, target)

def get_as_of_date(con: sqlite3.Connection) -> str:
    """Return the latest order or payment date - the demo's 'today'."""
    row = con.execute(
        "SELECT MAX(d) FROM ("
        " SELECT MAX(order_date) AS d FROM sales_orders"
        " UNION SELECT MAX(payment_date) FROM payments)"
    ).fetchone()
    return row[0]


def get_next_order_id(con: sqlite3.Connection) -> int:
    """Return the next free order id (one more than the biggest existing id)."""
    row = con.execute("SELECT MAX(id) FROM sales_orders").fetchone()
    return row[0] + 1

def get_customer_summaries(con: sqlite3.Connection, as_of: str) -> list[dict]:
    """For every confirmed shop: credit limit, money owed, worst overdue days, orders in the last year."""
    sql = """
        SELECT c.id, c.name, c.credit_limit,
               COALESCE(SUM(CASE WHEN o.status = 'delivered'
                                 THEN o.total - o.paid_amount ELSE 0 END), 0) AS open_balance,
               COALESCE(MAX(CASE WHEN o.status = 'delivered' AND o.total - o.paid_amount > 0.005
                                 THEN julianday(?) - julianday(o.due_date) END), 0) AS worst_days_overdue,
               COUNT(CASE WHEN o.order_date >= date(?, '-365 day') THEN 1 END) AS orders_last_year
        FROM customers c
        LEFT JOIN sales_orders o ON o.customer_id = c.id
        WHERE c.status = 'confirmed'
        GROUP BY c.id
        ORDER BY c.id
    """
    rows = con.execute(sql, (as_of, as_of)).fetchall()
    return [dict(r) for r in rows]

def pick_test_shops(summaries: list[dict]) -> dict[str, list[dict]]:
    """Sort shops into the test groups used for the demo orders."""
    good = [s for s in summaries
            if s["worst_days_overdue"] <= 0
            and s["open_balance"] < 0.5 * s["credit_limit"]
            and s["orders_last_year"] >= 20]
    over_limit = [s for s in summaries if s["open_balance"] > s["credit_limit"]]
    very_overdue = [s for s in summaries
                    if s["worst_days_overdue"] > 90
                    and s["open_balance"] <= s["credit_limit"]]
    return {
        "approve": good[:3],          # first 3 good shops
        "review": good[3:6],          # next 3 good shops (they'll get a giant order)
        "hold_limit": over_limit[:3],
        "hold_overdue": very_overdue[:3],
    }

def get_shop_details(con: sqlite3.Connection, customer_id: int, as_of: str) -> dict:
    """Credit days, home warehouse, average order value last year, and the rep of the latest order."""
    row = con.execute("""
        SELECT c.credit_days, c.home_warehouse_id,
               (SELECT AVG(total) FROM sales_orders
                 WHERE customer_id = c.id AND status = 'delivered'
                   AND order_date >= date(?, '-365 day')) AS avg_order,
               (SELECT created_by FROM sales_orders
                 WHERE customer_id = c.id ORDER BY order_date DESC LIMIT 1) AS rep_id
        FROM customers c WHERE c.id = ?""", (as_of, customer_id)).fetchone()
    return dict(row)

def get_active_items(con: sqlite3.Connection) -> list[dict]:
    """All products that are still on sale, with their prices."""
    rows = con.execute(
        "SELECT id, name, sale_price FROM items WHERE active = 1 ORDER BY id").fetchall()
    return [dict(r) for r in rows]

def build_lines(items: list[dict], target_subtotal: float) -> list[dict]:
    """Pick 4 random products and choose quantities so the subtotal lands near target_subtotal."""
    chosen = random.sample(items, 4)
    share = target_subtotal / 4          # each product gets about a quarter of the money
    lines = []
    for item in chosen:
        qty = max(1, round(share / item["sale_price"]))
        lines.append({
            "item_id": item["id"],
            "name": item["name"],
            "quantity": qty,
            "unit_price": item["sale_price"],
            "line_total": round(qty * item["sale_price"], 2),
        })
    return lines

def build_order(order_id: int, shop: dict, details: dict, as_of: str, lines: list[dict]) -> dict:
    """Assemble one order (not saved yet) with VAT and due date worked out."""
    subtotal = round(sum(line["line_total"] for line in lines), 2)
    tax = round(subtotal * VAT_RATE, 2)
    due = date.fromisoformat(as_of) + timedelta(days=details["credit_days"])
    return {
        "id": order_id,
        "order_no": f"SO-{order_id:06d}",
        "customer_id": shop["id"],
        "warehouse_id": details["home_warehouse_id"],
        "order_date": as_of,
        "due_date": due.isoformat(),
        "status": "to_confirm",
        "subtotal": subtotal,
        "tax_amount": tax,
        "total": round(subtotal + tax, 2),
        "paid_amount": 0.0,
        "created_by": details["rep_id"],
    }

def save_order(con: sqlite3.Connection, order: dict, lines: list[dict]) -> None:
    """Insert one order and its product lines into the copy."""
    con.execute("""
        INSERT INTO sales_orders (id, order_no, customer_id, warehouse_id, order_date, due_date,
                                  status, subtotal, tax_amount, total, paid_amount, created_by)
        VALUES (:id, :order_no, :customer_id, :warehouse_id, :order_date, :due_date,
                :status, :subtotal, :tax_amount, :total, :paid_amount, :created_by)""", order)
    for line in lines:
        con.execute("""
            INSERT INTO sales_order_lines (order_id, item_id, quantity, unit_price, line_total)
            VALUES (?, ?, ?, ?, ?)""",
            (order["id"], line["item_id"], line["quantity"], line["unit_price"], line["line_total"]))

def count_waiting_orders(con: sqlite3.Connection) -> int:
    """How many orders are waiting for a decision (status new or to_confirm)."""
    return con.execute(
        "SELECT COUNT(*) FROM sales_orders WHERE status IN ('to_confirm', 'new')").fetchone()[0]

def get_main_reps(con: sqlite3.Connection) -> dict[int, int]:
    """For each shop, the salesman who took most of its orders: {customer_id: user_id}."""
    rows = con.execute("""
        SELECT customer_id, created_by, COUNT(*) AS n
        FROM sales_orders
        GROUP BY customer_id, created_by
        ORDER BY customer_id, n DESC""").fetchall()
    main_reps = {}
    for r in rows:
        if r["customer_id"] not in main_reps:      # first row per shop = the rep with most orders
            main_reps[r["customer_id"]] = r["created_by"]
    return main_reps

def make_trn() -> str:
    """A fake 15-digit UAE TRN starting with 100 (the usual prefix)."""
    return "100" + "".join(str(random.randint(0, 9)) for _ in range(12))

def create_profile_table(con: sqlite3.Connection) -> None:
    """Make the ext_customer_profile table (deleting any old one first)."""
    con.execute("DROP TABLE IF EXISTS ext_customer_profile")
    con.execute("""
        CREATE TABLE ext_customer_profile (
            customer_id        INTEGER PRIMARY KEY,
            trn                TEXT,
            preferred_language TEXT NOT NULL,
            main_rep_id        INTEGER)""")

def build_profiles(con: sqlite3.Connection, main_reps: dict[int, int]) -> list[tuple]:
    """One (customer_id, trn, language, main_rep_id) row per shop."""
    profiles = []
    for (customer_id,) in con.execute("SELECT id FROM customers ORDER BY id").fetchall():
        trn = make_trn() if random.random() < 0.9 else None      # ~10% not VAT-registered
        language = "ar" if random.random() < 0.25 else "en"       # ~25% prefer Arabic
        profiles.append((customer_id, trn, language, main_reps.get(customer_id)))
    return profiles

def create_cheque_table(con: sqlite3.Connection) -> None:
    """Make the ext_cheque_details table (deleting any old one first)."""
    con.execute("DROP TABLE IF EXISTS ext_cheque_details")
    con.execute("""
        CREATE TABLE ext_cheque_details (
            payment_id   INTEGER PRIMARY KEY,
            cheque_no    TEXT NOT NULL,
            cheque_date  TEXT NOT NULL,
            bank         TEXT NOT NULL,
            status       TEXT NOT NULL CHECK (status IN ('cleared', 'pending')))""")

def build_cheques(con: sqlite3.Connection, as_of: str) -> list[tuple]:
    """One (payment_id, cheque_no, cheque_date, bank, status) row per cheque payment."""
    today = date.fromisoformat(as_of)
    cheques = []
    rows = con.execute(
        "SELECT id, payment_date FROM payments WHERE method = 'Cheque' ORDER BY id").fetchall()
    for r in rows:
        received = date.fromisoformat(r["payment_date"])
        days_ahead = random.choices([0, 15, 30, 45], weights=[70, 10, 15, 5])[0]
        cheque_date = received + timedelta(days=days_ahead)
        status = "pending" if cheque_date > today else "cleared"
        cheques.append((r["id"], f"{random.randint(0, 999999):06d}", cheque_date.isoformat(),
                        random.choice(UAE_BANKS), status))
    return cheques

def main() -> None:
    # Step 1.1 - make a fresh copy of the original database
    make_copy(SOURCE, TARGET)
    print(f"Copied {SOURCE} -> {TARGET}")

    # Step 1.2a - open the COPY and read two key facts
    con = sqlite3.connect(TARGET)
    con.row_factory = sqlite3.Row                    # rows readable by column name
    as_of = get_as_of_date(con)
    next_id = get_next_order_id(con)
    print(f"Data as of {as_of}; next order will be id {next_id} (SO-{next_id:06d})")
    print(f"Orders waiting before seeding: {count_waiting_orders(con)}")

    # Step 1.2b - summarise every shop, then pick the 12 test shops
    summaries = get_customer_summaries(con, as_of)
    groups = pick_test_shops(summaries)

    # Step 1.2c + 1.2d - build each order, preview it, and SAVE it
    random.seed(42)                                  # same "random" picks every run
    items = get_active_items(con)
    order_id = next_id
    with con:                                        # all-or-nothing save
        for group_name, shops in groups.items():
            print(f"\n{group_name}:")
            for shop in shops:
                details = get_shop_details(con, shop["id"], as_of)
                usual = details["avg_order"] or 1000.0           # fallback if no orders last year
                target = usual / (1 + VAT_RATE)                  # usual total is incl. VAT; lines are excl. VAT
                if group_name == "review":
                    target = target * 3                          # deliberately oversized order
                lines = build_lines(items, target)
                order = build_order(order_id, shop, details, as_of, lines)
                save_order(con, order, lines)
                print(f"  {order['order_no']}  {shop['name']:<30} usual {usual:>8,.0f}"
                      f"  this order {order['total']:>9,.2f}  due {order['due_date']}  rep {order['created_by']}")
                order_id += 1
    print(f"\nOrders waiting after seeding: {count_waiting_orders(con)}")

    # Step 1.3 - shop profiles (TRN, language, main salesman)
    random.seed(7)
    main_reps = get_main_reps(con)
    with con:
        create_profile_table(con)
        profiles = build_profiles(con, main_reps)
        con.executemany("INSERT INTO ext_customer_profile VALUES (?, ?, ?, ?)", profiles)
    stats = con.execute("""
        SELECT COUNT(*), SUM(trn IS NULL), SUM(preferred_language = 'ar'), SUM(main_rep_id IS NULL)
        FROM ext_customer_profile""").fetchone()
    print(f"\nShop profiles: {stats[0]} shops, {stats[1]} without TRN, "
          f"{stats[2]} prefer Arabic, {stats[3]} with no salesman")

    # Step 1.4 - cheque details for cheque payments
    random.seed(99)
    with con:
        create_cheque_table(con)
        cheques = build_cheques(con, as_of)
        con.executemany("INSERT INTO ext_cheque_details VALUES (?, ?, ?, ?, ?)", cheques)
    stats = con.execute("""
        SELECT COUNT(*), SUM(d.status = 'pending'),
               ROUND(SUM(CASE WHEN d.status = 'pending' THEN p.amount ELSE 0 END))
        FROM ext_cheque_details d JOIN payments p ON p.id = d.payment_id""").fetchone()
    print(f"Cheques: {stats[0]} recorded, {stats[1]} still pending, AED {stats[2]:,.0f} not yet cleared")

    con.close()


if __name__ == "__main__":
    main()