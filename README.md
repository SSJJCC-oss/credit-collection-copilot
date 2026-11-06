# Credit & Collections Copilot

An AI copilot for **credit control and collections** at wholesale distributors that sell to
shops on credit (UAE "van sales" businesses). It sits **beside** an existing billing system,
reads its data **read-only**, and helps office staff and managers decide what to do each day.

> **Status:** in progress. The rules engine and its tests are complete; the AI agents,
> API and dashboard are being built. See [Roadmap](#roadmap).

---

## What it does

| # | Feature | Example | Status |
|---|---|---|---|
| 1 | **Daily briefing** | "Shops owe AED 4.26M; AED 510k is 90+ days late. Chase Harbor View Supermarket first." | ✅ numbers · 🔜 AI summary |
| 2 | **Order approval assistant** | "HOLD SO-026777: owes AED 64,301 against a 37,000 limit; one bill is 660 days overdue." | ✅ rules · 🔜 AI explanation |
| 3 | **Payment reminder drafts** | Polite English / Arabic reminders with real invoice numbers, queued for human approval | 🔜 |
| 4 | **Ask your data** | "Which shops in Sharjah are more than 60 days overdue?" answered with a safe read-only query | ✅ safety guard · 🔜 AI |
| 5 | **Shops going quiet** | "Usually orders every 2 days; silent for 69 days; ~AED 82k/month at risk." | ✅ |

## Key design idea

**Python does the maths; the AI explains it.**
Every number and every APPROVE / HOLD / REVIEW decision comes from plain, tested Python.
The AI (Gemini via Google ADK) only picks which tool to call and turns results into plain English.
It never invents a figure and has no tool that can send, approve or change anything.

## Safety rules (enforced in code, not in prompts)

- The billing database is opened **read-only** (`mode=ro`). Writes are impossible.
- "Ask your data" runs **one SELECT only**, on **allow-listed tables and columns**, with a **row limit**.
  SQLite's own authorizer checks every table and column the query touches, including inside subqueries.
- Personal contact details and the test answer key are never visible to the AI.
- Nothing is sent without a person approving it; `DRY_RUN=true` by default.
- The copilot stores its own data (drafts, decisions, audit log) in a **separate** database.

---

## Quick start (Windows, PowerShell)

```powershell
git clone https://github.com/SSJJCC-oss/credit-collection-copilot.git
cd credit-collection-copilot
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env
python scripts\seed_demo.py      # builds the demo database from data\crm_demo.db
pytest -v                        # 69 tests, no API key needed
```

Requires Python 3.10+. On macOS/Linux use `source .venv/bin/activate` and `cp` instead of `copy`.

### Try it

```powershell
python -m scripts.try_query                                               # a safe "ask your data" query
python scripts\inspect_db.py data\crm_copilot_demo.db --out docs\DATA_PROFILE_SEEDED.md   # data report
```

---

## Project structure

```
├── ASSUMPTIONS.md      every assumption made, why, and how to change it
├── DESIGN.md           architecture, agents, tools, data model, safety rules
├── data/               crm_demo.db (fictional demo data); generated databases are not committed
├── docs/               data profile reports
├── scripts/            inspect_db.py (data report), seed_demo.py (demo data), try_query.py
├── copilot/            the rules engine (no AI)
│   ├── config.py         settings from .env
│   ├── db.py             read-only connection, "today" for the demo
│   ├── finance.py        what is owed, ageing, who to chase, over-limit shops, briefing
│   ├── credit_rules.py   APPROVE / HOLD / REVIEW with reasons
│   ├── quiet_shops.py    shops whose ordering has stopped
│   └── sql_guard.py      safe read-only queries
└── tests/              pytest tests (no API key needed)
```

## The demo data

`data/crm_demo.db` is **fictional**: a UAE food wholesaler with ~300 shops, 3 warehouses and
two years of orders and payments. `scripts/seed_demo.py` copies it (the original is never changed)
and adds:

- **12 test orders** waiting for approval, each designed to need APPROVE, REVIEW or HOLD
- **Shop profiles**: UAE TRN (tax number), preferred language (English/Arabic), main salesman
- **Cheque details**, including post-dated cheques not yet cleared

The tests check the copilot against these known answers. For example, all 12 test orders get the
expected decision, and the quiet-shop detector finds all 28 shops the data generator marked as churned.

## Tech stack

Python · SQLite · pytest · python-dotenv · *(coming)* Google ADK + Gemini · FastAPI · HTML/CSS/JS

---

## Roadmap

| Phase | What | Status |
|---|---|---|
| 0 | Inspect the database, understand the business flow | ✅ |
| 1 | Demo data seed script | ✅ |
| 2 | ASSUMPTIONS.md, DESIGN.md | ✅ |
| 3 | Rules engine + 69 tests (no AI) | ✅ |
| 4 | Copilot store: reminder drafts, approvals, audit log | 🔜 |
| 5 | Multi-agent AI (router + 4 specialists) and terminal chat with `--trace` | 🔜 |
| 6 | FastAPI backend and web dashboard | 🔜 |
| 7 | 3-minute demo script and video | 🔜 |

## Author

**Sanjay Jacob**, MEng Computer Vision & AI, University of Limerick
