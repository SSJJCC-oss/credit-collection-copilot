# Design

## 1. What it is

An AI copilot for **credit control and collections** at a wholesale distributor that sells
to shops on credit. It sits **beside** the billing system: it reads the billing data,
never changes it, and helps office staff and managers decide what to do.

| # | Feature | Who uses it | Output |
|---|---|---|---|
| 1 | Daily briefing | Manager | Total owed, overdue by age, top shops to chase, over-limit shops, AI summary |
| 2 | Order approval assistant | Office staff | APPROVE / HOLD / REVIEW for each waiting order, with reasons |
| 3 | Reminder drafts | Office staff | Polite reminders (English / Arabic) queued for a person to approve |
| 4 | Ask your data | Manager | Answers to plain-English questions from safe read-only queries |
| 5 | Shops going quiet | Sales manager | Shops that stopped ordering compared with their usual pattern |

**Key principle: Python does the maths; the AI explains it.**
Numbers and decisions come from plain, tested Python. The AI chooses which tool to call
and writes the explanation. It never invents a figure.

---

## 2. Architecture

```
                 ┌──────────────────────────────────────────────┐
  Users          │  Web dashboard (HTML/JS)   Terminal chat     │
                 │  ADK web UI (development)  (--trace mode)    │
                 └───────────────┬──────────────────────────────┘
                                 │ HTTP / function calls
                 ┌───────────────▼──────────────────────────────┐
  API            │  FastAPI backend  (/briefing, /orders,       │
                 │  /drafts, /drafts/{id}/approve, /chat)       │
                 └───────────────┬──────────────────────────────┘
                                 │
                 ┌───────────────▼──────────────────────────────┐
  AI layer       │  Router agent (Gemini via Google ADK)        │
                 │   ├─ Briefing agent      ─┐                  │
                 │   ├─ Credit agent         │ each wrapped     │
                 │   ├─ Collections agent    │ as an AgentTool  │
                 │   └─ Data Q&A agent      ─┘                  │
                 └───────────────┬──────────────────────────────┘
                                 │ calls plain Python tools
                 ┌───────────────▼──────────────────────────────┐
  Logic          │  finance · credit_rules · quiet_shops ·      │
                 │  reminders · sql_guard     (no AI, tested)   │
                 └──────┬───────────────────────────┬───────────┘
                        │ READ-ONLY                 │ read/write
                 ┌──────▼──────────────┐   ┌────────▼───────────┐
  Data           │ Billing data        │   │ Copilot store      │
                 │ crm_copilot_demo.db │   │ copilot.db         │
                 │ (never modified)    │   │ drafts, decisions, │
                 └─────────────────────┘   │ audit log          │
                                           └────────────────────┘
```

---

## 3. Agents

| Agent | Job | Tools it may use |
|---|---|---|
| **Router** (root) | Understands the request and hands it to the right specialist | The 4 specialists (as AgentTools) |
| **Briefing** | Daily credit & collections summary; quiet shops | `get_briefing`, `find_quiet_shops` |
| **Credit** | Recommends APPROVE / HOLD / REVIEW and explains why | `list_pending_orders`, `review_order`, `get_customer_overview` |
| **Collections** | Drafts payment reminders | `get_overdue_invoices`, `draft_reminder`, `list_drafts` |
| **Data Q&A** | Answers free questions with safe SQL | `describe_schema`, `run_safe_query` |

No agent has a tool that approves, sends or edits anything in the billing data.
Approving a reminder is done **only by a person** through the API or dashboard.

---

## 4. Tools (plain Python functions with clear docstrings)

| Tool | Returns |
|---|---|
| `get_briefing()` | Total owed, ageing buckets, top shops to chase, over-limit shops, pending cheques |
| `find_quiet_shops()` | Shops whose ordering has stopped vs their usual gap |
| `list_pending_orders()` | Orders with status `new` / `to_confirm` |
| `review_order(order_no)` | Decision + list of reasons + the numbers behind them |
| `get_customer_overview(customer)` | Limit, owed, overdue, payment history, usual order size |
| `get_overdue_invoices(customer)` | Unpaid bills with numbers, amounts, due dates |
| `draft_reminder(customer, language)` | Saves a draft (status `draft`) and returns its text |
| `list_drafts(status)` | Drafts in the approval queue |
| `describe_schema()` | Allow-listed tables and columns |
| `run_safe_query(sql)` | Rows from one checked, read-only SELECT |

---

## 5. Order decision rules (explainable, no AI)

Checked in order; every rule that fires is listed as a reason.

| Rule | Result |
|---|---|
| Money owed + this order > credit limit | HOLD |
| Any bill more than 90 days overdue | HOLD |
| Any bill 61–90 days overdue | REVIEW |
| This order > 2× the shop's usual order | REVIEW |
| None of the above | APPROVE |

The strongest result wins (HOLD > REVIEW > APPROVE). Thresholds are settings.
The AI only turns the reasons into plain English.

---

## 6. Data model

**Billing data** (`data/crm_copilot_demo.db`, opened read-only)
- `customers`, `sales_orders`, `sales_order_lines`, `payments`, `items`, `stock`,
  `warehouses`, `users`, `suppliers`, `purchase_orders`, `purchase_lines`, `expenses`
- Extensions added by the seed script: `ext_customer_profile` (TRN, language, main rep),
  `ext_cheque_details` (cheque no, date, bank, cleared/pending)
- `synthetic_notes`: test answer key, **never** visible to agents

**Copilot store** (`data/copilot.db`, the copilot's own database)

| Table | Holds |
|---|---|
| `reminder_drafts` | id, customer, language, channel, subject, body, invoices referenced, status (`draft` / `approved` / `rejected` / `logged`), who decided and when |
| `order_reviews` | order, recommendation, reasons, rule version, time |
| `audit_log` | every tool call: time, agent, tool, arguments, short result, success, duration |

---

## 7. Safety rules (enforced in code, not in prompts)

1. The billing database is opened with `mode=ro`; writes are impossible.
2. `run_safe_query` accepts exactly **one** `SELECT` statement, only on allow-listed
   tables and columns, and always adds a row limit (default 200).
3. The copilot writes only to its own `copilot.db`.
4. Nothing is sent without a person approving it. `DRY_RUN=true` by default: approved
   reminders are logged, never sent. Channels: email/SMS only, never WhatsApp.
5. Every tool call is written to `audit_log`.
6. Secrets (API key) live in `.env`, which is never committed.

---

## 8. Settings (`.env`)

| Setting | Default |
|---|---|
| `GEMINI_MODEL` | a current Gemini model name |
| `GOOGLE_API_KEY` | (your key) |
| `BILLING_DB` | `data/crm_copilot_demo.db` |
| `COPILOT_DB` | `data/copilot.db` |
| `AS_OF_DATE` | blank = latest date in the data |
| `CURRENCY` / `VAT_RATE` | `AED` / `0.05` |
| `DRY_RUN` | `true` |
| `MAX_QUERY_ROWS` | `200` |

---

## 9. Folder structure

```
├── ASSUMPTIONS.md  DESIGN.md  README.md  requirements.txt  .env.example
├── data/            crm_demo.db (original) + generated databases
├── scripts/         inspect_db.py, seed_demo.py
├── copilot/         config, db, finance, credit_rules, quiet_shops,
│                    reminders, sql_guard, audit, tools
├── agents/          ADK agents (router + specialists)
├── api/             FastAPI app
├── web/             dashboard (HTML, CSS, JS)
├── cli/             terminal chat with --trace
├── tests/           pytest tests (no API key needed)
└── demo/            3-minute demo script
```

---

## 10. Example: "Should we approve SO-026777?"

1. **Router** sees an order question and calls the **Credit agent**.
2. Credit agent calls `review_order("SO-026777")`.
3. `credit_rules` (Python) finds Golden Palm Catering owes AED 64,301 against a
   37,000 limit, and has a bill 660 days overdue → **HOLD**, 2 reasons.
4. The call is written to `audit_log`; the result is saved in `order_reviews`.
5. The agent writes: *"Hold this order. Golden Palm Catering already owes AED 64,301,
   well over its AED 37,000 limit, and one bill is almost two years overdue."*

---

## 11. Build phases

| Phase | Builds |
|---|---|
| 0–1 ✅ | Data inspection, demo seed data |
| 2 ✅ | ASSUMPTIONS.md, DESIGN.md |
| 3 | `copilot/` logic + pytest tests (no AI) |
| 4 | Copilot store + audit log |
| 5 | ADK agents + terminal chat (`--trace`) |
| 6 | FastAPI + web dashboard |
| 7 | README, demo script, demo video |