"""Unit tests for the agent's tools – no network, LLM or vector database needed."""

import copy
from datetime import date

import pytest

from energy_agent import catalog, tools


@pytest.fixture(autouse=True)
def fresh_customers(monkeypatch):
    """Give every test its own copy of the customers (meter readings mutate them)."""
    monkeypatch.setattr(tools, "CUSTOMERS", copy.deepcopy(catalog.CUSTOMERS))


def run(t, **kwargs) -> str:
    return t.invoke(kwargs)


# --- Accounts -----------------------------------------------------------------


@pytest.mark.parametrize("spoken", ["70012345", "70 01 23 45", "7001-2345", " 7001 2345. "])
def test_account_number_spoken_variants(spoken):
    assert "Emily Carter" in run(tools.get_account_summary, account_number=spoken)


def test_invalid_account_number():
    assert "8 digits" in run(tools.get_account_summary, account_number="12345")


def test_unknown_account():
    assert "No account found" in run(tools.get_account_summary, account_number="99999999")


def test_credit_balance():
    assert "£54.20 in credit" in run(tools.get_account_summary, account_number="70023456")


def test_overdue_balance():
    # Daniel Brooks' bill was due on 5 October 2026.
    out = run(tools.get_account_summary, account_number="70045678")
    assert "£212.75" in out
    assert ("overdue" in out) == (date.today() > date(2026, 10, 5))


# --- Meter readings -----------------------------------------------------------


def test_reading_lower_than_previous_is_rejected():
    assert "lower than the previous" in run(tools.submit_meter_reading, account_number="70023456", reading_kwh=9000)


def test_reading_is_recorded():
    out = run(tools.submit_meter_reading, account_number="70023456", reading_kwh=9400)
    assert "recorded" in out
    assert tools.CUSTOMERS["70023456"].last_reading_kwh == 9400
    assert tools.CUSTOMERS["70023456"].last_reading_date == date.today()


def test_implausible_reading_needs_confirmation():
    out = run(tools.submit_meter_reading, account_number="70023456", reading_kwh=99_999)
    assert "unusually high" in out
    assert tools.CUSTOMERS["70023456"].last_reading_kwh == 9310  # unchanged


def test_smart_meter_needs_no_reading():
    assert "smart meter" in run(tools.submit_meter_reading, account_number="70012345", reading_kwh=19000)


# --- Power cuts ---------------------------------------------------------------


@pytest.mark.parametrize("town", ["Leeds", "in Hull", "LEEDS.", "Kingston upon Hull"])
def test_current_power_cut(town):
    out = run(tools.check_power_cuts, town=town)
    assert "No current power cuts" not in out


def test_quiet_town():
    out = run(tools.check_power_cuts, town="Sheffield")
    assert "No current power cuts" in out and "No planned outages" in out


def test_town_outside_service_area():
    assert "105" in run(tools.check_power_cuts, town="Manchester")


# --- Tariffs ------------------------------------------------------------------


def test_annual_cost_formula():
    e7 = catalog.TARIFFS["Kestrel Economy 7"]
    expected = 1000 * (0.5 * 0.298 + 0.5 * 0.139) + 365 * 0.55
    assert catalog.annual_cost(e7, 1000, 0.5) == pytest.approx(expected)


def test_night_heavy_usage_prefers_economy_7():
    out = run(tools.compare_tariffs, annual_kwh=4000, night_share_percent=60)
    assert out.endswith("The cheapest is Kestrel Economy 7.")


def test_daytime_usage_prefers_fixed():
    out = run(tools.compare_tariffs, annual_kwh=1800, night_share_percent=10)
    assert "The cheapest is Kestrel Fixed." in out


def test_weekend_usage_prefers_weekend_saver():
    out = run(tools.compare_tariffs, annual_kwh=3000, night_share_percent=25, weekend_share_percent=40)
    assert "The cheapest is Kestrel Weekend Saver." in out


def test_green_premium_is_reported():
    out = run(tools.compare_tariffs, annual_kwh=2000, night_share_percent=10, prefers_green=True)
    assert "£34.00 more a year" in out  # 2000 kWh × (26.2p − 24.5p), same standing charge


def test_zero_usage_is_rejected():
    assert "above zero" in run(tools.compare_tariffs, annual_kwh=0)


@pytest.mark.parametrize(
    "name,expected",
    [("E7", "Kestrel Economy 7"), ("economy seven", "Kestrel Economy 7"), ("the green tariff", "Kestrel Green"),
     ("Kestrel Weekend Saver", "Kestrel Weekend Saver"), ("fixed", "Kestrel Fixed")],
)
def test_tariff_lookup(name, expected):
    assert run(tools.get_tariff_details, tariff_name=name).startswith(expected)


def test_unknown_tariff_lists_options():
    assert "Available tariffs" in run(tools.get_tariff_details, tariff_name="Platinum")


# --- Tickets ------------------------------------------------------------------


def test_ticket_ids_are_unique_and_recorded():
    before = len(tools.TICKETS)
    a = run(tools.create_support_ticket, reason="payment plan", account_number="7004 5678")
    b = run(tools.create_support_ticket, reason="payment plan")
    assert a.split()[2] != b.split()[2]
    assert tools.TICKETS[before]["account_number"] == "70045678"
