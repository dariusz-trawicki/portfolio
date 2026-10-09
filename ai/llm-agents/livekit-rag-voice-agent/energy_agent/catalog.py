"""Demo data for Kestrel Energy, a fictional UK electricity supplier.

This module is the single source of truth for both the agent's tools and the
PDF generator (`scripts/build_docs.py`), so the prices in the knowledge base
and the numbers the tools return can never drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

# ---------------------------------------------------------------------------
# Tariffs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Tariff:
    name: str
    meter_type: str  # "single-rate" or "two-rate"
    peak_rate: float  # £/kWh – the only rate on single-rate tariffs
    offpeak_rate: float | None  # £/kWh – cheaper rate on two-rate tariffs
    standing_charge: float  # £/day
    offpeak_hours: str
    green: bool
    perks: tuple[str, ...]
    best_for: str
    aliases: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_two_rate(self) -> bool:
        return self.offpeak_rate is not None


TARIFFS: dict[str, Tariff] = {
    t.name: t
    for t in (
        Tariff(
            name="Kestrel Fixed",
            meter_type="single-rate",
            peak_rate=0.245,
            offpeak_rate=None,
            standing_charge=0.53,
            offpeak_hours="none – one price around the clock",
            green=False,
            perks=("Unit rate fixed until 31 December 2027", "No exit fees in the last 49 days of the contract"),
            best_for="homes that use most of their electricity during the day",
            aliases=("fixed", "standard", "single rate", "single-rate", "flat"),
        ),
        Tariff(
            name="Kestrel Economy 7",
            meter_type="two-rate",
            peak_rate=0.298,
            offpeak_rate=0.139,
            standing_charge=0.55,
            offpeak_hours="7 hours every night, from 00:30 to 07:30",
            green=False,
            perks=("Cheap overnight electricity every day", "Ideal for storage heaters and overnight EV charging"),
            best_for="homes with storage heaters, a hot-water cylinder or an electric car charged overnight",
            aliases=("economy 7", "economy seven", "e7", "night", "overnight", "two rate", "two-rate"),
        ),
        Tariff(
            name="Kestrel Weekend Saver",
            meter_type="two-rate",
            peak_rate=0.305,
            offpeak_rate=0.152,
            standing_charge=0.57,
            offpeak_hours="every night from 00:30 to 07:30, plus all day Saturday and Sunday",
            green=False,
            perks=("Off-peak prices all weekend", "Pays off when laundry and cooking happen at weekends"),
            best_for="people who are out at work on weekdays and do most chores at the weekend",
            aliases=("weekend", "weekend saver", "weekends"),
        ),
        Tariff(
            name="Kestrel Green",
            meter_type="single-rate",
            peak_rate=0.262,
            offpeak_rate=None,
            standing_charge=0.53,
            offpeak_hours="none – one price around the clock",
            green=True,
            perks=(
                "100% renewable electricity backed by REGO certificates",
                "Annual green-energy certificate for your home",
            ),
            best_for="customers who want their electricity matched with renewable generation",
            aliases=("green", "renewable", "eco", "green energy"),
        ),
    )
}


def find_tariff(query: str) -> Tariff | None:
    """Match a tariff by name or alias, case-insensitively."""
    q = " ".join(query.lower().replace("tariff", "").replace("kestrel", "").split())
    if not q:
        return None
    for tariff in TARIFFS.values():
        short_name = tariff.name.lower().removeprefix("kestrel ").strip()
        if q == short_name or q in tariff.aliases:
            return tariff
    # Loose match, e.g. "the economy 7 one" or "weekend saver plan"
    for tariff in TARIFFS.values():
        short_name = tariff.name.lower().removeprefix("kestrel ").strip()
        if short_name in q or any(f" {alias} " in f" {q} " for alias in tariff.aliases):
            return tariff
    return None


def annual_cost(tariff: Tariff, annual_kwh: float, offpeak_share: float) -> float:
    """Estimated yearly cost in £ including standing charges.

    `offpeak_share` is the fraction (0–1) of consumption that falls inside the
    tariff's off-peak window; it is ignored for single-rate tariffs.
    """
    offpeak_share = min(max(offpeak_share, 0.0), 1.0)
    if tariff.is_two_rate:
        energy = annual_kwh * ((1 - offpeak_share) * tariff.peak_rate + offpeak_share * tariff.offpeak_rate)
    else:
        energy = annual_kwh * tariff.peak_rate
    return round(energy + 365 * tariff.standing_charge, 2)


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------


@dataclass
class Customer:
    account_number: str
    name: str
    town: str
    tariff: str
    balance_gbp: float  # > 0: amount owed, < 0: account in credit
    due_date: date | None
    last_reading_kwh: int
    last_reading_date: date
    avg_monthly_kwh: int
    smart_meter: bool
    direct_debit: bool


CUSTOMERS: dict[str, Customer] = {
    c.account_number: c
    for c in (
        Customer("70012345", "Emily Carter", "Leeds", "Kestrel Economy 7", 86.40,
                 date(2026, 10, 20), 18452, date(2026, 9, 30), 310, True, True),
        Customer("70023456", "James Whitfield", "York", "Kestrel Fixed", -54.20,
                 None, 9310, date(2026, 8, 31), 220, False, False),
        Customer("70034567", "Priya Shah", "Sheffield", "Kestrel Green", 0.0,
                 None, 4120, date(2026, 9, 30), 180, True, True),
        Customer("70045678", "Daniel Brooks", "Hull", "Kestrel Weekend Saver", 212.75,
                 date(2026, 10, 5), 27703, date(2026, 9, 15), 340, False, False),
    )
}


# ---------------------------------------------------------------------------
# Network status (service area: Yorkshire)
# ---------------------------------------------------------------------------

SERVICE_AREA: dict[str, dict] = {
    "leeds": {
        "display": "Leeds",
        "active": ["Underground cable fault in Headingley affecting parts of Otley Road – power expected back by 6 pm."],
        "planned": ["14 October, 9 am to 2 pm – substation upgrade in Roundhay, Street Lane and surrounding roads."],
    },
    "york": {
        "display": "York",
        "active": [],
        "planned": ["16 October, 10 am to 1 pm – transformer replacement in Acomb."],
    },
    "sheffield": {"display": "Sheffield", "active": [], "planned": []},
    "bradford": {
        "display": "Bradford",
        "active": [],
        "planned": ["21 October, 8 am to 3 pm – overhead line works in Thornton, Market Street and Hill Top Road."],
    },
    "hull": {
        "display": "Hull",
        "active": ["Storm damage to an overhead line in Sutton-on-Hull – engineers are on site and expect to restore power within 3 hours."],
        "planned": [],
    },
}

# Common speech-to-text variants.
TOWN_ALIASES = {
    "kingston upon hull": "hull",
    "kingston-upon-hull": "hull",
    "sheffield city": "sheffield",
}


def normalize_town(raw: str) -> str:
    key = raw.lower().strip(" .,!?")
    for prefix in ("in ", "near ", "around "):
        if key.startswith(prefix):
            key = key[len(prefix):]
    return TOWN_ALIASES.get(key, key)
