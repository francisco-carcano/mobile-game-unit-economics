import math
from dataclasses import replace

import pytest

import unit_economics as ue


@pytest.fixture
def assumptions():
    return ue.load_assumptions()


@pytest.fixture
def base(assumptions):
    return ue.scenario_at(assumptions, ue.MID, costs_eur=100.0)


def test_retention_curve_passes_through_d1_and_d30(base):
    assert ue.retention(0, base.d1, base.d30) == 1.0
    assert math.isclose(ue.retention(1, base.d1, base.d30), base.d1)
    assert math.isclose(ue.retention(30, base.d1, base.d30), base.d30)


def test_retention_decreases_with_age(base):
    values = [ue.retention(age, base.d1, base.d30) for age in range(1, 90)]
    assert all(a > b for a, b in zip(values, values[1:]))


def test_revenue_scales_linearly_with_installs(base):
    single = ue.monthly_revenue_eur(replace(base, installs_per_day=1.0), 6)
    double = ue.monthly_revenue_eur(replace(base, installs_per_day=2.0), 6)
    assert math.isclose(double, 2 * single)


def test_break_even_installs_cover_costs_exactly(base):
    needed = ue.break_even_installs(base, month=12)
    assert math.isclose(ue.monthly_net_eur(replace(base, installs_per_day=needed), 12), 0.0, abs_tol=1e-6)


def test_monthly_costs_add_optional_items(assumptions):
    plain = ue.monthly_costs(assumptions, "basic")
    with_extras = ue.monthly_costs(assumptions, "basic", self_employed="reduced_rate", ios=True)
    costs = assumptions["monthly_costs_eur"]
    assert math.isclose(with_extras - plain, costs["self_employed_fee"]["reduced_rate"] + costs["apple_developer"]["value"])


def test_lifetime_value_matches_its_components(base):
    expected = (ue.active_days_per_install(base) * ue.ad_revenue_per_active_day_eur(base)
                + ue.purchase_revenue_per_install_eur(base))
    assert math.isclose(ue.lifetime_value_eur(base), expected)
    assert ue.active_days_per_install(base, days=1) == 1.0


def test_steady_state_revenue_converges_to_installs_times_lifetime_value(base):
    """After a year, a month of revenue ~ a month of installs times their first-year value."""
    s = replace(base, d30=base.d1 * 0.05)  # fast decay so the one-year window captures almost everything
    monthly = ue.monthly_revenue_eur(s, 13)
    approx = s.installs_per_day * ue.DAYS_PER_MONTH * ue.lifetime_value_eur(s)
    assert math.isclose(monthly, approx, rel_tol=0.05)
