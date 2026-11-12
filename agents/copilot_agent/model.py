"""model.py - which Gemini model the agents use, with automatic retries when Google is busy."""
from google.adk.models.google_llm import Gemini
from google.genai import types

from copilot.config import load_settings


def make_model() -> Gemini:
    """The Gemini model named in .env (GEMINI_MODEL), retrying on 429 (rate limit) and 503 (busy)."""
    return Gemini(
        model=load_settings().gemini_model,
        retry_options=types.HttpRetryOptions(
            attempts=5,              # try up to 5 times in total
            initial_delay=2,         # wait 2 seconds before the first retry...
            max_delay=30,            # ...doubling each time, but never more than 30 seconds
            http_status_codes=[429, 503],
        ),
    )