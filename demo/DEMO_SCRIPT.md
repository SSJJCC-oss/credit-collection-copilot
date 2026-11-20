# 3-minute demo script

**Story:** a wholesale distributor's office starts the day. The copilot tells them where the money is,
which orders are risky, writes the reminders, and answers questions, while a person stays in control.

---

## Before the demo (5 minutes)

1. Open a terminal in the project folder and activate the venv: `.venv\Scripts\Activate.ps1`
2. Fresh demo data (optional but recommended):
   ```powershell
   python scripts\seed_demo.py
   Remove-Item data\copilot.db -ErrorAction SilentlyContinue
   ```
3. Check the Google login works: `gcloud auth application-default login` (only if it has been a while).
4. Start the app: `uvicorn api.main:app --port 8001`
5. Open **http://127.0.0.1:8001/** in the browser, press **Ctrl + F5**, zoom to 110–125% so it is readable on a shared screen.
6. Warm up the AI once: on **Ask**, send "Should we approve SO-026777?" and wait for the answer.
   Then refresh the page so the chat is empty again.
7. Close other tabs and notifications. Share **only the browser window**.

---

## The demo

### 0:00–0:20 · The problem
**Say:** "Wholesale distributors sell to hundreds of shops on credit. Their biggest daily headache is late
payments: who owes what, which new orders are safe to approve, and chasing people politely. Their billing
software records everything, but it doesn't tell the office what to do next. That's what this copilot does."

### 0:20–0:50 · Daily briefing (Briefing screen)
**Show:** the 4 cards, the ageing bars, the two tables.
**Say:** "Shops owe 4.26 million dirhams, and 2.4 million of it is overdue. Half a million is more than 90 days
late; that's the red bar. 24 shops are over their credit limit. The copilot ranks who to chase first by
amount *and* lateness, so Harbor View Supermarket is top. On the right, shops that have stopped ordering:
Happy Family Hypermarket normally orders every two days and has been silent for 69 days, about 82,000
dirhams a month at risk."

### 0:50–1:30 · An order put on hold (Orders screen)
**Show:** the cards (15 waiting: 6 approve, 3 review, 6 hold). **Click SO-026777** (Golden Palm Catering).
**Say:** "15 orders are waiting for approval. Each gets a recommendation from fixed, tested credit rules,
not from the AI's opinion. Golden Palm Catering's order is on HOLD, and here's exactly why: they already owe
64,000 against a 37,000 limit, one bill is 660 days overdue, and they pay 95 days late on average."
**Click SO-026775** (REVIEW): "This one isn't risky in debt terms, but the order is three times the shop's
usual size, so a person should check it."

### 1:30–2:20 · A reminder drafted and approved (Reminders screen)
**Do:** type **Golden Palm Catering** → **Create draft**.
**Say:** "The copilot writes the reminder from the real invoices: invoice numbers, amounts, due dates, the
customer's tax number, and their salesman's name. It can also write it in Arabic. Because their oldest bill
is so late, the tone is firm. And notice: it has **not** been sent."
**Do:** click **Approve** with the name box empty → point at the error. Type your name → **Approve**.
**Say:** "Only a named person can approve. In demo mode it's logged, not sent, so nothing ever leaves without
a human decision."

### 2:20–2:50 · A question in plain English (Ask screen)
**Do:** click **"Which shops in Sharjah are more than 60 days overdue?"**
**Say (while it thinks):** "A router agent passes the question to the right specialist. This one writes a
database query, and every query is checked by a safety guard: read-only, approved tables only, no
private data."
**When the answer appears:** point at the grey line: "Answered by the data agent, and here are the exact
tools it used."

### 2:50–3:00 · Close
**Say:** "Python does the maths, the AI explains it, and a person stays in control. It's read-only on the
billing data, every action is in an audit log, and it plugs into an existing system through an API."

---

## If something goes wrong

| Problem | What to do |
|---|---|
| The AI is slow (> 10 s) | Keep talking about the safety design; it usually answers within ~20 s |
| Red "AI service could not answer" | Say "the AI service is unavailable for a moment", and show the **Orders** and **Reminders** screens instead: they don't need the AI. Afterwards: `gcloud auth application-default login` and restart |
| "A reminder is already waiting" | That's fine: it opens the existing draft. Approve that one |
| Page looks old or unstyled | **Ctrl + F5** |
| Server not running | `uvicorn api.main:app --port 8001` |
| No internet at all | Run `python -m scripts.demo_today` in the terminal: it shows the briefing, orders, safety guard and quiet shops with no AI |

---

## Questions people often ask

- **"Does the AI make the decisions?"** No. Tested Python rules decide; the AI explains and chooses which
  tool to use. It has no tool that can approve, send or change data.
- **"Can it change the billing data?"** No. The billing database is opened read-only, and the copilot keeps its
  own separate database for drafts, decisions and the audit log.
- **"Is the data real?"** No, it's a fictional UAE distributor (about 300 shops, two years of orders).
- **"How would it connect to a real billing system?"** Through the API: their pages can show the briefing,
  order badges and approval queue, and only the database connection needs changing.
- **"What does it cost to run?"** A light Gemini model; a typical day's questions cost cents.