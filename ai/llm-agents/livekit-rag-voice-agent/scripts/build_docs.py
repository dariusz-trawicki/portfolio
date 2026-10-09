"""Generate the Kestrel Energy knowledge-base PDFs into docs/.

Tariff prices and the list of towns come from energy_agent/catalog.py, so the
documents and the agent's tools stay in sync whenever the price list changes.

Usage:  python scripts/build_docs.py
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # noqa: E402

from energy_agent.catalog import SERVICE_AREA, TARIFFS  # noqa: E402

BRAND = colors.HexColor("#0F766E")
TINT = colors.HexColor("#CCFBF1")
INK = colors.HexColor("#1F2937")
MUTED = colors.HexColor("#6B7280")

Styles = dict[str, ParagraphStyle]


def styles() -> Styles:
    base = ParagraphStyle("body", fontName="Helvetica", fontSize=10.5, leading=15, textColor=INK, spaceAfter=6)
    bold = "Helvetica-Bold"
    return {
        "brand": ParagraphStyle("brand", parent=base, fontName=bold, fontSize=11, textColor=BRAND),
        "title": ParagraphStyle("title", parent=base, fontName=bold, fontSize=20, leading=26, spaceAfter=4),
        "subtitle": ParagraphStyle("subtitle", parent=base, textColor=MUTED, spaceAfter=14),
        "h1": ParagraphStyle("h1", parent=base, fontName=bold, fontSize=14, leading=19, textColor=BRAND, spaceBefore=12),
        "h2": ParagraphStyle("h2", parent=base, fontName=bold, fontSize=11.5, spaceBefore=8, spaceAfter=3),
        "body": base,
    }


def table(rows: list[list[str]], widths: list[float], s: Styles) -> Table:
    cell = ParagraphStyle("cell", parent=s["body"], fontSize=9.5, leading=13, spaceAfter=0)
    head = ParagraphStyle("head", parent=cell, fontName="Helvetica-Bold", textColor=colors.white)
    data = [[Paragraph(c, head) for c in rows[0]]] + [[Paragraph(c, cell) for c in r] for r in rows[1:]]
    t = Table(data, colWidths=[w * cm for w in widths], hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BRAND),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, TINT]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E5E7EB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return t


def p(rate_gbp: float) -> str:
    return f"{rate_gbp * 100:g}p"


def faq(s: Styles, items: list[tuple[str, str]]) -> list:
    out: list = []
    for question, answer in items:
        out += [Paragraph(question, s["h2"]), Paragraph(answer, s["body"])]
    return out


def build(filename: str, title: str, subtitle: str, story_fn: Callable[[Styles], list]) -> None:
    s = styles()
    story = [
        Paragraph("KESTREL ENERGY", s["brand"]),
        Spacer(1, 4),
        Paragraph(title, s["title"]),
        Paragraph(subtitle, s["subtitle"]),
        *story_fn(s),
    ]
    out = ROOT / "docs" / filename
    out.parent.mkdir(exist_ok=True)
    SimpleDocTemplate(
        str(out), pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm, topMargin=2 * cm,
        bottomMargin=2 * cm, title=title, author="Kestrel Energy (fictional company)",
    ).build(story)
    print(f"[OK] {out.relative_to(ROOT)}")


# ---------------------------------------------------------------------------
# 1. Tariffs and prices
# ---------------------------------------------------------------------------


def tariffs_story(s: Styles) -> list:
    rows = [["Tariff", "Meter", "Unit rate", "Standing charge"]]
    for t in TARIFFS.values():
        rate = (
            f"{p(t.peak_rate)}/kWh day<br/>{p(t.offpeak_rate)}/kWh off-peak"
            if t.is_two_rate
            else f"{p(t.peak_rate)}/kWh at all times"
        )
        rows.append([t.name, t.meter_type, rate, f"{p(t.standing_charge)} per day"])

    story: list = [
        Paragraph(
            "Kestrel Energy supplies electricity to homes across Yorkshire. All prices in this guide include VAT at 5%. "
            "Your bill is made up of two parts: the unit rate you pay for each kilowatt-hour (kWh) you use, and a daily "
            "standing charge that covers the cost of keeping your home connected to the grid.",
            s["body"],
        ),
        Paragraph("Tariffs at a glance", s["h1"]),
        table(rows, [4.4, 2.6, 5.0, 3.6], s),
    ]

    for t in TARIFFS.values():
        if t.is_two_rate:
            rates = (
                f"Day rate: {p(t.peak_rate)} per kWh. Off-peak rate: {p(t.offpeak_rate)} per kWh. "
                f"Off-peak hours: {t.offpeak_hours}."
            )
        else:
            rates = f"Single unit rate: {p(t.peak_rate)} per kWh at any time of day."
        story += [
            Paragraph(t.name, s["h1"]),
            Paragraph(f"A {t.meter_type} tariff. Best for {t.best_for}.", s["body"]),
            Paragraph(rates, s["body"]),
            Paragraph(f"Standing charge: {p(t.standing_charge)} per day. Perks: {'; '.join(t.perks)}.", s["body"]),
        ]

    story += [
        Paragraph("Choosing the right tariff", s["h1"]),
        table(
            [
                ["How you use electricity", "Suggested tariff", "Why"],
                ["Mostly during the day, little running overnight", "Kestrel Fixed", "Lowest single rate, price fixed until the end of 2027"],
                ["Storage heaters, hot-water cylinder or EV charged overnight – at least 35% of use at night", "Kestrel Economy 7", "Seven hours of cheap electricity every night"],
                ["Out at work on weekdays, chores and cooking at weekends", "Kestrel Weekend Saver", "Off-peak prices all day Saturday and Sunday"],
                ["Renewable electricity matters most", "Kestrel Green", "100% renewable, backed by REGO certificates"],
            ],
            [6.2, 3.6, 5.8],
            s,
        ),
        Paragraph(
            "A two-rate tariff only saves money if enough of your usage falls in the off-peak window. For a typical home, "
            "Economy 7 starts to pay off when roughly 35% of usage is overnight, and Weekend Saver when roughly 43% falls "
            "overnight or at weekends. Below that, the higher day rate and standing charge cancel out the savings.",
            s["body"],
        ),
        Paragraph("Changing tariff", s["h1"]),
        Paragraph(
            "You can change tariff free of charge once every 12 months in the Kestrel app or by speaking to our customer team. "
            "The new tariff starts on the first day of your next billing month. Moving from a single-rate to a two-rate tariff "
            "needs a compatible meter; if you have a smart meter we switch it remotely, otherwise we book a free meter exchange.",
            s["body"],
        ),
    ]
    return story


# ---------------------------------------------------------------------------
# 2. Billing, payments and meter readings
# ---------------------------------------------------------------------------


def billing_story(s: Styles) -> list:
    return [
        Paragraph("Bills", s["h1"]),
        *faq(s, [
            ("How often will I get a bill?",
             "Every month. Customers with a smart meter are always billed on actual usage. Customers with a traditional meter "
             "are billed on their latest reading, or on an estimate if we haven't had one."),
            ("What is an estimated bill?",
             "If we don't have a recent reading, we estimate your usage from your history. Estimated bills are marked with an 'E' "
             "next to the reading. As soon as you send a reading, the next bill corrects any difference."),
            ("Why is my bill higher than usual?",
             "The most common reasons are: a previous estimate that was too low, higher winter usage from heating and lighting, "
             "a new appliance such as a heat pump, tumble dryer or electric car, or the end of a fixed-price contract. "
             "The Usage tab in the Kestrel app shows month-by-month consumption."),
            ("My account is in credit. Can I get the money back?",
             "Yes. Credit is normally used against your next bills, but you can ask for a refund at any time and we will pay it "
             "to your bank account within 10 working days."),
        ]),
        Paragraph("Meter readings", s["h1"]),
        *faq(s, [
            ("How do I submit a meter reading?",
             "In the Kestrel app, through our voice assistant, or by texting READ followed by your account number and reading to 60040. "
             "Send the reading within the last 5 days of your billing month. Give the whole numbers only, ignoring anything after "
             "the decimal point or in red."),
            ("I have a smart meter. Do I need to send readings?",
             "No. Smart meters send readings automatically. If the app shows that your meter hasn't reported for more than "
             "a month, contact us and we'll check the connection."),
            ("What if I have a two-rate meter?",
             "Two-rate meters show two readings, usually labelled 'low' or 'night' and 'normal' or 'day'. Send both."),
        ]),
        Paragraph("Payments", s["h1"]),
        *faq(s, [
            ("How can I pay?",
             "By monthly Direct Debit, by debit or credit card in the app, by bank transfer quoting your account number, or in cash "
             "at any PayPoint. Paying by Direct Debit is the cheapest option and gives a £5 discount on every bill."),
            ("How is my Direct Debit amount worked out?",
             "We spread your expected yearly cost evenly across 12 months, so you pay the same in summer and winter. "
             "We review it every 6 months and tell you before any change."),
            ("What happens if I miss a payment?",
             "We'll send a reminder after 7 days. If you're struggling to pay, please talk to us early – we'll always offer a "
             "payment plan that fits your budget before taking any further action, and we never charge late-payment fees."),
            ("Can I spread the cost of a large bill?",
             "Yes. Our customer team can set up a payment plan over 3 to 12 months with no extra cost. The voice assistant can raise "
             "a request and the team will call you back."),
        ]),
        Paragraph("Complaints and switching", s["h1"]),
        *faq(s, [
            ("How do I make a complaint?",
             "Through the app, by email, by phone or via the voice assistant. We aim to resolve complaints within 5 working days. "
             "If we can't resolve your complaint within 8 weeks, or you're unhappy with our final response, you can take it to the "
             "Energy Ombudsman free of charge."),
            ("How do I switch to Kestrel Energy?",
             "Just sign up – we handle everything with your old supplier. Switching usually takes around 5 working days, "
             "your supply isn't interrupted, and you don't need a new meter."),
            ("Are there exit fees?",
             "Kestrel Economy 7, Weekend Saver and Green have no exit fees. Kestrel Fixed has an exit fee of £50 if you leave more "
             "than 49 days before the end of the fixed period."),
        ]),
    ]


# ---------------------------------------------------------------------------
# 3. Power cuts and the network
# ---------------------------------------------------------------------------


def network_story(s: Styles) -> list:
    towns = ", ".join(a["display"] for a in SERVICE_AREA.values())
    return [
        Paragraph(
            "Kestrel Energy is your electricity supplier. The cables, substations and meters are run by the regional network "
            f"operator, which is responsible for fixing power cuts. We share live outage information for {towns}.",
            s["body"],
        ),
        Paragraph("My power is off – what should I do?", s["h1"]),
        Paragraph(
            "1. Check your fuse box: if a switch has tripped, unplug appliances and reset it. "
            "2. Check whether your neighbours have power – if they don't, it's likely a power cut. "
            "3. Check the outage map in the Kestrel app or ask our voice assistant. "
            "4. Call 105, the free national power-cut number, to report it or get updates.",
            s["body"],
        ),
        Paragraph(
            "Safety first: if you smell burning, see sparks or a fallen power line, keep well away, don't touch anything, and "
            "call 999. Customers who rely on electricity for medical equipment should join the Priority Services Register.",
            s["body"],
        ),
        Paragraph("Planned outages", s["h1"]),
        Paragraph(
            "The network operator gives at least 2 days' notice of planned work. We post it in the Kestrel app and text affected "
            "customers who have notifications turned on. Planned work usually lasts between 4 and 8 hours.",
            s["body"],
        ),
        Paragraph("Compensation for long power cuts", s["h1"]),
        Paragraph(
            "If an unplanned power cut lasts longer than 12 hours in normal weather, you may be entitled to a compensation "
            "payment from the network operator. Our customer team can help you claim.",
            s["body"],
        ),
        Paragraph("Smart meters", s["h1"]),
        Paragraph(
            "Smart meters are installed free of charge. They send readings automatically, so every bill is based on actual use, "
            "and they let you see your half-hourly consumption in the app. Book an installation in the app or ask the customer team.",
            s["body"],
        ),
    ]


def main() -> None:
    build("kestrel-tariffs-and-prices.pdf", "Tariffs and Prices", "Effective 1 October 2026 · prices include VAT", tariffs_story)
    build("kestrel-billing-and-payments.pdf", "Billing, Payments and Meter Readings", "Frequently asked questions", billing_story)
    build("kestrel-power-cuts-and-network.pdf", "Power Cuts and the Network", "Customer information · October 2026", network_story)


if __name__ == "__main__":
    main()
