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
