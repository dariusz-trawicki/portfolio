"""LangChain tools used by the Kestrel Energy agent.

Every tool returns a short, speakable English sentence or two – amounts in
pounds and pence, dates with month names – so the LLM can relay results
naturally on a voice call.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime

from langchain_core.tools import tool

from energy_agent.catalog import (
    CUSTOMERS,
    SERVICE_AREA,
    TARIFFS,
    annual_cost,
    find_tariff,
    normalize_town,
)

# Tickets handed to the human team (a CRM / helpdesk in a real system).
TICKETS: list[dict] = []

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def gbp(amount: float) -> str:
    """1234.5 -> '£1,234.50'"""
    return f"£{amount:,.2f}"


def pence(rate_gbp: float) -> str:
    """0.245 -> '24.5p per kWh'"""
    return f"{rate_gbp * 100:g}p per kWh"


def spoken_date(d: date) -> str:
    return f"{d.day} {d:%B %Y}"


def normalize_account_number(raw: str) -> str | None:
    """Speech-to-text often splits numbers up ('70 01 23 45', '7001-2345'),
    so keep the digits only."""
    digits = re.sub(r"\D", "", raw or "")
    return digits if len(digits) == 8 else None


INVALID_NUMBER = (
    "Account numbers have 8 digits and appear at the top of every bill. "
    "Ask the customer to repeat their account number."
)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool
def search_knowledge_base(question: str) -> str:
    """Search Kestrel Energy's documentation: tariffs and prices, billing and
    payments FAQ, meter readings, switching, complaints, power cuts and smart
    meters. Use it for any general question about policies or procedures."""
    from energy_agent.rag import format_passages, retrieve

    passages = retrieve(question)
    if not passages:
        return "Nothing relevant in the documentation. Offer to pass the question to the customer team."
    return format_passages(passages)


@tool
def get_account_summary(account_number: str) -> str:
    """Look up a customer's account: balance (amount owed or credit), due
    date, tariff, latest meter reading and average usage.
    Requires the 8-digit account number from the customer's bill."""
    number = normalize_account_number(account_number)
    if number is None:
        return INVALID_NUMBER
    c = CUSTOMERS.get(number)
    if c is None:
        return f"No account found for {number}. Ask the customer to check the number on their bill."

    if c.balance_gbp > 0:
        balance = f"Amount owed: {gbp(c.balance_gbp)}"
        if c.due_date:
            if c.due_date < date.today():
                balance += f", which was due on {spoken_date(c.due_date)} and is now overdue"
            else:
                balance += f", due on {spoken_date(c.due_date)}"
    elif c.balance_gbp < 0:
        balance = f"The account is {gbp(-c.balance_gbp)} in credit, which will be used against the next bill"
    else:
        balance = "The account is fully paid up"

    meter = "smart meter, read automatically" if c.smart_meter else "traditional meter, read by the customer"
    payment = "pays by Direct Debit" if c.direct_debit else "pays on receipt of bill"
    return (
        f"Customer: {c.name}, {c.town}. {balance}. "
        f"Tariff: {c.tariff}; {payment}. "
        f"Latest reading: {c.last_reading_kwh} kWh on {spoken_date(c.last_reading_date)} ({meter}). "
        f"Average usage: about {c.avg_monthly_kwh} kWh a month."
    )


@tool
def submit_meter_reading(account_number: str, reading_kwh: int) -> str:
    """Record a meter reading given by the customer (the whole-number kWh
    figure on the meter). Requires the 8-digit account number."""
    number = normalize_account_number(account_number)
    if number is None:
        return INVALID_NUMBER
    c = CUSTOMERS.get(number)
    if c is None:
        return f"No account found for {number}."
    if c.smart_meter:
        return "This customer has a smart meter – readings are sent automatically, so there is no need to submit one."

    if reading_kwh < c.last_reading_kwh:
        return (
            f"The reading {reading_kwh} is lower than the previous reading of {c.last_reading_kwh}. "
            "Ask the customer to check the meter again."
        )

    days = max((date.today() - c.last_reading_date).days, 1)
    expected = c.avg_monthly_kwh * days / 30
    consumed = reading_kwh - c.last_reading_kwh
    if consumed > max(3 * expected, 500):
        return (
            f"That would mean {consumed} kWh used since the last reading, which is unusually high. "
            "Ask the customer to confirm the figure; if it is correct, raise a ticket for the customer team."
        )

    c.last_reading_kwh = reading_kwh
    c.last_reading_date = date.today()
    return (
        f"Reading of {reading_kwh} kWh recorded. That's {consumed} kWh since the previous reading, "
        "and the next bill will be based on it."
    )


@tool
def check_power_cuts(town: str) -> str:
    """Check current power cuts and planned outages in a town.
    Covered: Leeds, York, Sheffield, Bradford, Hull."""
    area = SERVICE_AREA.get(normalize_town(town))
    if area is None:
        covered = ", ".join(a["display"] for a in SERVICE_AREA.values())
        return (
            f"We don't hold network data for {town} (we cover {covered}). "
            "Anyone in Great Britain can report or check a power cut by calling 105, free of charge."
        )

    current = " ".join(area["active"]) or "No current power cuts."
    planned = " ".join(area["planned"]) or "No planned outages in the next two weeks."
    return f"{area['display']}. Current: {current} Planned: {planned}"


@tool
def compare_tariffs(
    annual_kwh: int,
    night_share_percent: int = 15,
    weekend_share_percent: int = 0,
    prefers_green: bool = False,
) -> str:
    """Estimate the yearly cost of every tariff for the customer's usage and
    name the cheapest.
    annual_kwh: yearly usage (a typical flat uses 1,800, a house 2,700–4,000).
    night_share_percent: share of usage between 00:30 and 07:30.
    weekend_share_percent: extra share used during the day at weekends.
    prefers_green: whether renewable electricity matters to the customer."""
    if annual_kwh <= 0:
        return "Annual usage must be above zero. Ask for the figure on the customer's annual statement."

    night = night_share_percent / 100
    weekend = weekend_share_percent / 100
    costs = sorted(
        (
            (annual_cost(t, annual_kwh, night + weekend if t.name == "Kestrel Weekend Saver" else night), t)
            for t in TARIFFS.values()
        ),
        key=lambda item: (item[0], item[1].name),  # Tariff itself is not orderable
    )

    cheapest_cost, cheapest = costs[0]
    lines = "; ".join(f"{t.name} about {gbp(cost)} a year" for cost, t in costs)
    result = (
        f"Estimate for {annual_kwh:,} kWh a year, including standing charges: {lines}. "
        f"The cheapest is {cheapest.name}."
    )

    if prefers_green and not cheapest.green:
        green_cost, green = next((cost, t) for cost, t in costs if t.green)
        result += f" {green.name} would cost about {gbp(green_cost - cheapest_cost)} more a year."
    return result


@tool
def get_tariff_details(tariff_name: str) -> str:
    """Details of one tariff: unit rates, off-peak hours, standing charge and
    perks. Accepts a full name ('Kestrel Economy 7') or a short one ('E7', 'green')."""
    t = find_tariff(tariff_name)
    if t is None:
        return f"There is no tariff called '{tariff_name}'. Available tariffs: {', '.join(TARIFFS)}."

    if t.is_two_rate:
        rates = (
            f"day rate {pence(t.peak_rate)}, off-peak rate {pence(t.offpeak_rate)}; "
            f"off-peak hours: {t.offpeak_hours}"
        )
    else:
        rates = f"single unit rate of {pence(t.peak_rate)} around the clock"

    return (
        f"{t.name} ({t.meter_type}): {rates}. "
        f"Standing charge {t.standing_charge * 100:g}p per day. "
        f"Perks: {'; '.join(t.perks)}. "
        f"Best for {t.best_for}."
    )


@tool
def create_support_ticket(reason: str, account_number: str = "") -> str:
    """Hand the case to the human customer team – complaints, billing
    disputes, payment plans, contract changes, or when the customer asks for a
    person. The account number is optional."""
    ticket_id = "KE-" + uuid.uuid4().hex[:6].upper()
    TICKETS.append(
        {
            "id": ticket_id,
            "created": datetime.now().isoformat(timespec="seconds"),
            "account_number": normalize_account_number(account_number),
            "reason": reason,
        }
    )
    print(f"[TICKET] {TICKETS[-1]}")
    spelled = " ".join(ticket_id.replace("-", ""))
    return (
        f"Created ticket {ticket_id}. Someone from the customer team will call back within 4 working hours. "
        f"When reading the reference out, spell it character by character: {spelled}."
    )


ALL_TOOLS = [
    search_knowledge_base,
    get_account_summary,
    submit_meter_reading,
    check_power_cuts,
    compare_tariffs,
    get_tariff_details,
    create_support_ticket,
]
