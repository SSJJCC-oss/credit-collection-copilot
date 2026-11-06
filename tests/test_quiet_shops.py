"""Tests for copilot/quiet_shops.py - no API key needed."""
from datetime import date, timedelta

from copilot.db import connect_billing_readonly, get_as_of_date
from copilot.quiet_shops import check_shop, find_quiet_shops, usual_gap_days


def weekly_shop(last_order: str, orders: int = 10) -> dict:
    """A hand-made shop that ordered exactly every 7 days, ending on `last_order`."""
    last = date.fromisoformat(last_order)
    dates = [(last - timedelta(days=7 * i)).isoformat() for i in reversed(range(orders))]
    return {"customer_id": 1, "customer_name": "Weekly Shop", "city": "Dubai",
            "dates": dates, "totals": [700.0] * orders}


def test_usual_gap_for_weekly_orders():
    assert usual_gap_days(weekly_shop("2026-10-01")["dates"]) == 7


def test_too_few_orders_has_no_rhythm():
    assert usual_gap_days(["2026-01-01", "2026-01-08", "2026-01-15"]) is None


def test_same_day_orders_count_as_at_least_one_day():
    assert usual_gap_days(["2026-01-01"] * 6) == 1


def test_weekly_shop_silent_for_50_days_is_quiet():
    result = check_shop(weekly_shop("2026-09-05"), "2026-10-25")    # 50 days, ~7x the gap
    assert result["days_silent"] == 50
    assert result["is_quiet"] is True
    assert result["monthly_value"] == 3000.0                         # 700 per order x 30/7


def test_weekly_shop_silent_for_20_days_is_fine():
    assert check_shop(weekly_shop("2026-10-05"), "2026-10-25")["is_quiet"] is False


def test_short_silence_is_ignored_even_for_daily_shops():
    shop = weekly_shop("2026-10-15")
    shop["dates"] = [(date(2026, 10, 15) - timedelta(days=i)).isoformat() for i in reversed(range(10))]
    result = check_shop(shop, "2026-10-25")                          # 10 days = 10x a daily gap...
    assert result["is_quiet"] is False                               # ...but under the 45-day minimum


def test_finds_every_churned_shop_in_demo_data():
    con = connect_billing_readonly()
    quiet_ids = {s["customer_id"] for s in find_quiet_shops(con, get_as_of_date(con))}
    # The answer key is only ever read here, in a test - never by the copilot itself.
    churned = {r[0] for r in con.execute("SELECT ref_id FROM synthetic_notes WHERE kind = 'churned'")}
    con.close()
    assert churned <= quiet_ids                  # every churned shop is found
    assert len(quiet_ids - churned) <= 5         # and only a handful of extra alerts