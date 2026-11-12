# Credit & Collections Copilot

An AI copilot for **credit control and collections** at wholesale distributors that sell to
shops on credit, such as UAE "van sales" businesses. It sits **beside** an existing billing
system, reads its data **read-only**, and helps office staff and managers decide what to do
each day: who to chase, which orders to approve, and what to send.

---

## Features

| # | Feature | Example |
|---|---|---|
| 1 | **Daily briefing** | "Shops owe AED 4.26M; AED 510k is more than 90 days late. Chase Harbor View Supermarket first." |
| 2 | **Order approval assistant** | "HOLD SO-026777: Golden Palm Catering owes AED 64,301 against a 37,000 limit, and one bill is 660 days overdue." |
| 3 | **Payment reminder drafts** | Polite English or Arabic reminders with the shop's real invoice numbers, amounts and due dates, queued for a person to approve |
| 4 | **Ask your data** | "Which shops in Sharjah are more than 60 days overdue?" answered from a safe, read-only query |
| 5 | **Shops going quiet** | "Usually orders every 2 days; silent for 69 days; about AED 82k a month at risk." |

## Key design idea

**Python does the maths; the AI explains it.**

Every figure and every APPROVE / HOLD / REVIEW decision comes from plain, tested Python rules.
The AI (Gemini via Google ADK) chooses which tool to call and turns the results into plain English.
It never invents a number, and it has no tool that can send a message, approve anything,
or change the billing data.

---

## How it works

```
  Web dashboard · Terminal chat (--trace) · ADK web UI
                        │
                  FastAPI backend
                        │
        Router agent (Gemini via Google ADK)
   ┌──────────┬─────────┴────────┬──────────────┐
Briefing    Credit         Collections       Data Q&A        ← specialist agents
   └──────────┴─────────┬────────┴──────────────┘
          Plain Python tools (no AI, fully tested)
     finance · credit_rules · quiet_shops · reminders · sql_guard
            │                                  │
   Billing database (READ-ONLY)        Copilot database
                                       drafts · decisions · audit log
```

- **Router agent:** understands the request and hands it to the right specialist.
- **Briefing agent:** daily summary and quiet shops.
- **Credit agent:** order recommendations with reasons.
- **Collections agent:** reminder drafts.
- **Data Q&A agent:** answers questions with safe SQL.

Each specialist can use only the tools it needs.

## Order decision rules

| Rule | Result |
|---|---|
| Money owed + this order > credit limit | HOLD |
| Any bill more than 90 days overdue | HOLD |
| Any bill 61–90 days overdue | REVIEW |
| This order > 2× the shop's usual order | REVIEW |
| Pays on average more than 45 days late | REVIEW |
| None of the above | APPROVE |

Every rule that fires is shown as a reason, and the strongest result wins. All thresholds are settings.

## Safety rules (enforced in code, not in prompts)

- The billing database is opened **read-only**. Writes are impossible.
- "Ask your data" runs **one SELECT only**, on **allow-listed tables and columns**, with a **row limit**.
  SQLite's own authorizer checks every table and column a query touches, including inside subqueries.
- Personal contact details and the test answer key are never visible to the AI.
- **Nothing is sent without a person approving it.** `DRY_RUN=true` by default: approved reminders are logged, not sent. Email/SMS only.
- The copilot keeps its own data (drafts, decisions, audit log of every tool call) in a **separate** database.
- Secrets live in `.env`, which is never committed.

---

## Getting started (Windows, PowerShell)

Requires **Python 3.10+** and a **Google Gemini API key** (only for the AI features; the tests don't need one).

```powershell
git clone https://github.com/SSJJCC-oss/credit-collection-copilot.git
cd credit-collection-copilot
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env           # then add your Gemini API key to .env
python scripts\seed_demo.py      # builds the demo database from data\crm_demo.db
```

On macOS/Linux use `source .venv/bin/activate` and `cp` instead of `copy`.

### Run it

```powershell
pytest -v                          # all tests (no API key needed)
python -m cli.chat                 # chat with the copilot in the terminal
python -m cli.chat --trace         # ...and see every agent and tool call
uvicorn api.main:app --reload      # API + web dashboard at http://127.0.0.1:8000
adk web agents                     # Google ADK development UI
```

### Settings (`.env`)

| Setting | Meaning | Default |
|---|---|---|
| `GOOGLE_API_KEY` | Your Gemini API key | |
| `GEMINI_MODEL` | Which Gemini model to use | |
| `BILLING_DB` | Billing database (opened read-only) | `data/crm_copilot_demo.db` |
| `COPILOT_DB` | The copilot's own database | `data/copilot.db` |
| `AS_OF_DATE` | The copilot's "today" (blank = latest date in the data) | |
| `CURRENCY` / `VAT_RATE` | Currency and VAT | `AED` / `0.05` |
| `DRY_RUN` | Log approved reminders instead of sending them | `true` |
| `MAX_QUERY_ROWS` | Row limit for "Ask your data" | `200` |

---

## Project structure

```
├── ASSUMPTIONS.md    every assumption made, why, and how to change it
├── DESIGN.md         architecture, agents, tools, data model, safety rules
├── data/             crm_demo.db (fictional demo data); generated databases are not committed
├── docs/             data profile reports
├── scripts/          inspect_db.py (data report), seed_demo.py (demo data)
├── copilot/          rules engine and tools (no AI): finance, credit rules, quiet shops,
│                     reminders, SQL guard, audit log, settings
├── agents/           router + specialist agents (Google ADK)
├── api/              FastAPI backend
├── web/              dashboard (HTML, CSS, JavaScript)
├── cli/              terminal chat with --trace mode
├── tests/            pytest tests (no API key needed)
└── demo/             3-minute demo script
```

## Demo data

`data/crm_demo.db` is **fictional**: a UAE food wholesaler with about 300 shops, 3 warehouses
and two years of orders and payments. `scripts/seed_demo.py` copies it (the original is never
changed) and adds:

- **Test orders waiting for approval**, each designed to need APPROVE, REVIEW or HOLD
- **Shop profiles:** UAE TRN (tax number), preferred language (English/Arabic), main salesman
- **Cheque details**, including post-dated cheques not yet cleared

The tests check the copilot against these known answers: every test order must get its expected
decision, and the quiet-shop detector must find every shop the data generator marked as churned.

## Tech stack

Python · Google ADK · Gemini · FastAPI · SQLite · pytest · HTML / CSS / JavaScript

## Author

**Sanjay Jacob**
