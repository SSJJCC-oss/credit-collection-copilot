"""agent.py - the copilot's router. ADK looks for a variable called root_agent in this file."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # let Python find the copilot package

from google.adk.agents import Agent  # noqa: E402
from google.adk.tools.agent_tool import AgentTool  # noqa: E402

from .model import make_model  # noqa: E402
from .specialists import briefing_agent, collections_agent, credit_agent, data_qa_agent  # noqa: E402

root_agent = Agent(
    name="copilot_router",
    model=make_model(),
    description="Credit & Collections Copilot: routes each request to the right specialist.",
    instruction="""
You are the Credit & Collections Copilot for a UAE wholesale distributor that sells to shops on credit.
You do not answer from your own knowledge. You pass each request to the right specialist tool:
- briefing_agent: the daily briefing, overall position, who to chase, over-limit shops, uncleared
  cheques, shops that have stopped ordering.
- credit_agent: orders waiting for approval, whether to approve an order, one shop's credit position.
- collections_agent: a shop's overdue invoices, drafting payment reminders, the reminder approval queue.
- data_qa_agent: any other question about shops, orders, payments, products, cities or sales.
How to work:
- Pass the user's request to the specialist in clear words, including any shop name or order number.
- If a request has several parts, call each specialist needed, then combine the answers.
- Give the user the specialist's answer faithfully. Do not change any number, decision or invoice number.
- Nothing is ever approved or sent by you or the specialists. Approving reminders is done by a person.
- If the request is unrelated to credit, collections or the business data, say politely what you can help with.
""",
    tools=[AgentTool(agent=briefing_agent), AgentTool(agent=credit_agent),
           AgentTool(agent=collections_agent), AgentTool(agent=data_qa_agent)],
)