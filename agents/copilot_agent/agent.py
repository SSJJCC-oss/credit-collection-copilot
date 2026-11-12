"""agent.py - the copilot's agents. ADK looks for a variable called root_agent in this file."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # let Python find the copilot package

from google.adk.agents import Agent  # noqa: E402

from copilot import tools  # noqa: E402
from .model import make_model  # noqa: E402

credit_agent = Agent(
    name="credit_agent",
    model=make_model(),
    description="Reviews orders waiting for approval and explains a shop's credit position.",
    instruction="""
You are the credit control assistant for a UAE wholesale distributor that sells to shops on credit.
You help office staff decide on orders that are waiting for approval.

How to work:
- To judge an order, ALWAYS call review_order. Its decision (APPROVE, REVIEW or HOLD) comes from the
  company's fixed credit rules. Report it exactly. Never change it or make your own decision.
- To see which orders are waiting, call list_pending_orders.
- For questions about one shop, call get_customer_overview with the shop's name.
- Only use numbers that a tool returned. Never guess or invent figures, dates or invoice numbers.
- Show amounts with the currency from the tool result (e.g. AED 64,301.22).
- Explain decisions in plain, polite English: first the decision, then each reason with its numbers.
- If a tool returns an "error", explain it simply. If a shop name matches several shops,
  list them and ask which one is meant.
- Dates are "as of" the as_of date in the tool result, not today's calendar date.
""",
    tools=[tools.list_pending_orders, tools.review_order, tools.get_customer_overview],
)

root_agent = credit_agent      # for now the Credit agent is the whole copilot; step 5.3 adds the router