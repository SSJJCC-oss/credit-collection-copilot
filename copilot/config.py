"""config.py - every setting the copilot uses, read once from the .env file."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _as_bool(value: str) -> bool:
    """Turn text like 'true', 'yes' or '1' into True; anything else into False."""
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    billing_db: Path
    copilot_db: Path
    as_of_date: str | None
    currency: str
    vat_rate: float
    dry_run: bool
    max_query_rows: int


def load_settings() -> Settings:
    """Read every setting from the environment (.env), using safe defaults."""
    return Settings(
        billing_db=PROJECT_ROOT / os.getenv("BILLING_DB", "data/crm_copilot_demo.db"),
        copilot_db=PROJECT_ROOT / os.getenv("COPILOT_DB", "data/copilot.db"),
        as_of_date=os.getenv("AS_OF_DATE") or None,
        currency=os.getenv("CURRENCY", "AED"),
        vat_rate=float(os.getenv("VAT_RATE", "0.05")),
        dry_run=_as_bool(os.getenv("DRY_RUN", "true")),
        max_query_rows=int(os.getenv("MAX_QUERY_ROWS", "200")),
    )