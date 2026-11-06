"""Tests for copilot/db.py and copilot/config.py - no API key needed."""
import sqlite3

import pytest

from copilot.config import load_settings
from copilot.db import connect_billing_readonly, get_as_of_date


def test_default_settings():
    s = load_settings()
    assert s.currency == "AED"
    assert s.vat_rate == 0.05
    assert s.dry_run is True


def test_billing_database_is_read_only():
    con = connect_billing_readonly()
    with pytest.raises(sqlite3.OperationalError):
        con.execute("DELETE FROM customers")
    con.close()


def test_as_of_date_is_latest_date_in_data():
    con = connect_billing_readonly()
    assert get_as_of_date(con) == "2026-10-25"
    con.close()


def test_missing_database_gives_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        connect_billing_readonly(tmp_path / "nope.db")