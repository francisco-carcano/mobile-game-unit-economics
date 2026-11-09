"""Unit economics of an ad-funded casual mobile game.

Revenue = active users x ad impressions x eCPM, plus one-off "remove ads" purchases.
Active users come from constant daily installs and a power-law retention curve
fitted through D1 and D30. Costs are monthly. All results are gross, before tax.

Usage: python src/unit_economics.py   (regenerates results.md)
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSUMPTIONS_PATH = ROOT / "assumptions.json"
RESULTS_PATH = ROOT / "results.md"
DAYS_PER_MONTH = 30
LOW, MID, HIGH = 0, 1, 2
LEVELS = (("Pessimistic", LOW), ("Mid", MID), ("Optimistic", HIGH))


@dataclass(frozen=True)
class Scenario:
    installs_per_day: float
    d1: float
    d30: float
    impressions_per_dau: float
    ecpm_usd: float
    purchase_rate: float
    price_eur: float
    store_fee: float
    eur_per_usd: float
    monthly_costs_eur: float


def load_assumptions(path: Path = ASSUMPTIONS_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def monthly_costs(a: dict, tooling: str, self_employed: str | None = None, ios: bool = False) -> float:
    costs = a["monthly_costs_eur"]
    total = costs["tooling"][tooling] + costs["other"]["value"]
    if self_employed:
        total += costs["self_employed_fee"][self_employed]
    if ios:
        total += costs["apple_developer"]["value"]
    return total


def scenario_at(a: dict, level: int, costs_eur: float) -> Scenario:
    r = a["revenue"]
    return Scenario(
        installs_per_day=r["installs_per_day"]["range"][level],
        d1=r["retention_d1"]["range"][level],
        d30=r["retention_d30"]["range"][level],
        impressions_per_dau=r["ad_impressions_per_dau"]["range"][level],
        ecpm_usd=r["ecpm_usd"]["range"][level],
        purchase_rate=r["remove_ads_purchase_rate"]["range"][level],
        price_eur=r["remove_ads_price_eur"]["range"][level],
        store_fee=r["store_fee"]["value"],
        eur_per_usd=r["eur_per_usd"]["value"],
        monthly_costs_eur=costs_eur,
    )


def retention(age_days: int, d1: float, d30: float) -> float:
    """Share of a cohort still active `age_days` after install (day 0 = 1)."""
    if age_days == 0:
        return 1.0
    exponent = math.log(d1 / d30) / math.log(30)
    return d1 * age_days ** (-exponent)


def daily_active_users(s: Scenario, day: int) -> float:
    """Active users on `day` when installs started on day 0 at a constant rate."""
    return s.installs_per_day * sum(retention(age, s.d1, s.d30) for age in range(day + 1))


def ad_revenue_per_active_day_eur(s: Scenario) -> float:
    return s.impressions_per_dau * s.ecpm_usd / 1000 * s.eur_per_usd


def purchase_revenue_per_install_eur(s: Scenario) -> float:
    return s.purchase_rate * s.price_eur * (1 - s.store_fee)


def monthly_revenue_eur(s: Scenario, month: int) -> float:
    first_day = (month - 1) * DAYS_PER_MONTH
    dau_days = sum(daily_active_users(s, d) for d in range(first_day, first_day + DAYS_PER_MONTH))
    installs = s.installs_per_day * DAYS_PER_MONTH
    return dau_days * ad_revenue_per_active_day_eur(s) + installs * purchase_revenue_per_install_eur(s)


def monthly_net_eur(s: Scenario, month: int) -> float:
    return monthly_revenue_eur(s, month) - s.monthly_costs_eur


def break_even_installs(s: Scenario, month: int = 12) -> float:
    """Daily installs needed for revenue to cover costs in `month` (revenue is linear in installs)."""
    return s.monthly_costs_eur / monthly_revenue_eur(replace(s, installs_per_day=1.0), month)


def active_days_per_install(s: Scenario, days: int = 365) -> float:
    return sum(retention(age, s.d1, s.d30) for age in range(days))


def lifetime_value_eur(s: Scenario, days: int = 365) -> float:
    """Revenue one install generates over its first `days` days."""
    return active_days_per_install(s, days) * ad_revenue_per_active_day_eur(s) + purchase_revenue_per_install_eur(s)


def paid_cpi_eur(a: dict) -> float:
    return a["acquisition"]["paid_cpi_usd"]["value"] * a["revenue"]["eur_per_usd"]["value"]


def sensitivity(a: dict, costs_eur: float, month: int = 12) -> list[tuple[str, float, float]]:
    """Month-`month` revenue when each assumption moves alone to its low and high value."""
    base = scenario_at(a, MID, costs_eur)
    fields = {
        "installs_per_day": "installs_per_day",
        "retention_d1": "d1",
        "retention_d30": "d30",
        "ad_impressions_per_dau": "impressions_per_dau",
        "ecpm_usd": "ecpm_usd",
        "remove_ads_purchase_rate": "purchase_rate",
        "remove_ads_price_eur": "price_eur",
    }
    rows = []
    for name, field in fields.items():
        low, _, high = a["revenue"][name]["range"]
        rows.append((name,
                     monthly_revenue_eur(replace(base, **{field: low}), month),
                     monthly_revenue_eur(replace(base, **{field: high}), month)))
    return sorted(rows, key=lambda row: row[2] - row[1], reverse=True)


def report() -> str:
    a = load_assumptions()
    costs = monthly_costs(a, "standard")
    last_day = 12 * DAYS_PER_MONTH - 1
    cpi = paid_cpi_eur(a)
    lines = ["# Results (generated by `src/unit_economics.py`)", "",
             "Gross figures, before tax. Month 12, standard tooling cost, not self-employed, unless stated.", ""]

    lines += ["## Value of an install vs the cost of buying one", "",
              "| Scenario | Active days per install (first year) | Revenue per install (first year) | Paid install cost | Revenue / cost |",
              "| --- | --- | --- | --- | --- |"]
    for label, level in LEVELS:
        s = scenario_at(a, level, costs)
        ltv = lifetime_value_eur(s)
        lines.append(f"| {label} | {active_days_per_install(s):.1f} | EUR {ltv:.2f} | EUR {cpi:.2f} | {ltv / cpi:.0%} |")

    lines += ["", "## Scenarios", "",
              "| Scenario | Daily active users | Revenue/month | Costs/month | Net/month |", "| --- | --- | --- | --- | --- |"]
    for label, level in LEVELS:
        s = scenario_at(a, level, costs)
        lines.append(f"| {label} | {daily_active_users(s, last_day):,.0f} | EUR {monthly_revenue_eur(s, 12):,.0f} | "
                     f"EUR {costs:,.0f} | EUR {monthly_net_eur(s, 12):,.0f} |")

    lines += ["", "## Daily installs needed to break even (other assumptions at mid values)", "",
              "| Cost structure | Costs/month | Installs/day |", "| --- | --- | --- |"]
    for label, tooling, fee in (("Basic tooling", "basic", None), ("Standard tooling", "standard", None),
                                ("Premium tooling", "premium", None),
                                ("Standard + self-employed (reduced rate)", "standard", "reduced_rate"),
                                ("Standard + self-employed (general minimum)", "standard", "minimum_general")):
        c = monthly_costs(a, tooling, fee)
        lines.append(f"| {label} | EUR {c:,.0f} | {break_even_installs(scenario_at(a, MID, c)):,.0f} |")

    lines += ["", "## Net result by daily installs (other assumptions at mid values)", "",
              "| Installs/day | Daily active users | Revenue/month | Net/month |", "| --- | --- | --- | --- |"]
    for installs in (1, 5, 12, 25, 50, 100, 200, 500):
        s = replace(scenario_at(a, MID, costs), installs_per_day=installs)
        lines.append(f"| {installs} | {daily_active_users(s, last_day):,.0f} | EUR {monthly_revenue_eur(s, 12):,.0f} | "
                     f"EUR {monthly_net_eur(s, 12):,.0f} |")

    lines += ["", "## Sensitivity: month-12 revenue moving one assumption at a time", "",
              "| Assumption | At low value | At high value |", "| --- | --- | --- |"]
    for name, low, high in sensitivity(a, costs):
        lines.append(f"| {name} | EUR {low:,.0f} | EUR {high:,.0f} |")

    s = scenario_at(a, MID, costs)
    lines += ["", f"Retention curve check (mid values): modelled D7 = {retention(7, s.d1, s.d30):.1%}, "
              "against a 10-15% benchmark (AppAgent)."]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    RESULTS_PATH.write_text(report(), encoding="utf-8")
    print(RESULTS_PATH.read_text(encoding="utf-8"))
