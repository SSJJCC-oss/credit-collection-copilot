# Assumptions

The copilot was built only from screenshots of the billing system, its public website,
and a fictional demo database. Wherever something was unknown, a sensible assumption
was made and recorded here. Each entry says **why** and **how to change it**.

Status: ✅ in use · 🔜 planned for a later phase

---

## A. How the business data works

**A1. "Today" is the last date in the data (2026-10-25), not the real date.** ✅
- Why: the demo data stops on 25 Oct 2026. Measuring from the real date would make every bill look later than it is.
- Where: `get_as_of_date()` in `scripts/seed_demo.py`.
- Change: Phase 3 adds an `AS_OF_DATE` setting in `.env` (blank = latest date in data).

**A2. A delivered order is the invoice.** ✅
- Why: there is no invoices table. For all 26,770 orders, `due_date = order_date + customer credit_days`, so the order date is the invoice date and `order_no` (e.g. SO-026768) is the bill number.
- Change: if the real system has a separate invoices table, point the copilot's queries at it.

**A3. Money owed = delivered orders only.** ✅
- Why: confirmed / new / to_confirm orders have not been delivered, so no bill exists yet. They count as *upcoming exposure* against the credit limit, not as money owed.
- Note: the database view `v_outstanding_orders` also includes confirmed orders. The copilot does not use that view for this reason.

**A4. Credit days = 0 means cash on delivery.** ✅
- Why: 74 shops have 0 credit days; their due date equals their order date.

**A5. Credit period is measured in days.** ✅
- Why: the New Customer form labels it "Credit Period" and the data stores whole numbers (0–60).

**A6. Overdue age is counted from the due date, in these buckets:** not yet due · 1–30 · 31–60 · 61–90 · 90+ days. ✅
- Change: bucket edges become a setting in Phase 3.

**A7. Orders with status `new` or `to_confirm` are both "waiting for a decision".** ✅
- Why: the dashboard shows "New Orders (2)" and "Orders to Confirm (1)", matching these statuses exactly.

**A8. Shops with status `pending` are excluded from credit analysis.** ✅
- Why: they are new registrations not yet approved ("Customers to Confirm (4)"), and none have orders.

**A9. Currency is AED and VAT is 5%.** ✅
- Why: every order's tax is exactly 5% of its subtotal.
- Where: `VAT_RATE` in `scripts/seed_demo.py`; Phase 3 moves currency and VAT into `.env`.

**A10. A shop's main salesman is the rep who took most of its orders.** ✅
- Why: there is no shop-to-salesman table; `sales_orders.created_by` records who took each order.
- Where: `get_main_reps()`.

**A11. Near-duplicate shops (ids 301–303) are kept as they are.** ✅
- Why: the copilot never changes the billing data. It may *flag* likely duplicates for a person to merge.

**A12. The table `synthetic_notes` is a test answer key and is hidden from the AI.** ✅
- Why: it labels late payers, churned shops and duplicates. If the AI could read it, it would "cheat".
- Use: only in automated tests, to check the copilot finds the right shops.

---

## B. Demo data added by `scripts/seed_demo.py`

All demo data is added to a **copy** (`data/crm_copilot_demo.db`). The original
`data/crm_demo.db` is never changed. New tables start with `ext_` and the billing
system's own tables keep their original structure.

**B1. 12 test orders waiting for approval (SO-026771 to SO-026782).** ✅
- 3 *approve*: nothing overdue, owes < 50% of limit, 20+ orders last year.
- 3 *review*: same kind of shop, but the order is 3× its usual size.
- 3 *hold_limit*: shop already owes more than its credit limit.
- 3 *hold_overdue*: a bill > 90 days overdue, but under the limit.
- Dated on the as-of date; status `to_confirm`; normal orders sized to the shop's average delivered order over the last year (fallback AED 1,000).
- Change: the rules are in `pick_test_shops()`; the size in `main()`.

**B2. Shop profiles (`ext_customer_profile`).** ✅
- TRN: fake 15-digit number starting `100`; ~10% of shops have none (below the VAT registration threshold).
- Preferred language: ~25% Arabic, the rest English (random).
- Main salesman: see A10.

**B3. Cheque details (`ext_cheque_details`).** ✅
- Every cheque payment gets a cheque number, bank and cheque date.
- 70% are dated the day they are received; 30% are post-dated by 15, 30 or 45 days.
- A cheque dated after the as-of date is `pending` (received but not yet in the bank).
- **No bounced cheques**: a bounced cheque would mean the payment never happened, which would contradict the billing system's `paid_amount`. The copilot never edits those tables.

**B4. Fixed random seeds (42, 7, 99) make the demo identical every run.** ✅

---

## C. Decisions for later phases

**C1. Order decision rules (draft values, Phase 3).** 🔜
- HOLD if (money owed + this order) > credit limit, or any bill > 90 days overdue.
- REVIEW if this order > 2× the shop's usual order, or any bill 61–90 days overdue.
- APPROVE otherwise.
- All numbers become settings so a manager can tune them.

**C2. "Going quiet" rule (draft, Phase 3).** 🔜
- Flag a shop if the days since its last order are more than 3× its usual gap between orders, and at least 21 days.

**C3. Reminders are never sent automatically.** 🔜
- Every draft needs a person to approve it. `DRY_RUN=true` by default: approved reminders are only logged.
- Email/SMS only, never WhatsApp. Shops with no email or phone are flagged instead.

**C4. "Ask your data" safety.** 🔜
- Read-only database connection; one `SELECT` statement only; allow-listed tables and columns; row limit.
- `synthetic_notes` is never on the allow-list.

**C5. The AI model name is a setting in `.env`.** 🔜
- Automatic retries on 429 (rate limit) and 503 (busy) errors.  