"""Draws the README chart from the model. Usage: python docs/make_chart.py"""
import sys
from dataclasses import replace
from pathlib import Path

import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import unit_economics as ue  # noqa: E402

THEMES = {
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", grid="#e1e0d9", base="#c3c2b7", series="#2a78d6", ref="#e34948"),
    "dark": dict(surface="#1a1a19", ink="#f0efec", ink2="#c3c2b7", grid="#2c2c2a", base="#383835", series="#3987e5", ref="#e66767"),
}
OUT_DIR = Path(__file__).resolve().parent / "figures"


def style(ax, t):
    ax.set_facecolor(t["surface"])
    ax.tick_params(colors=t["ink2"], labelsize=9, length=0)
    for side in ax.spines.values():
        side.set_visible(False)
    ax.grid(axis="y", color=t["grid"], linewidth=0.8)
    ax.set_axisbelow(True)


def draw(name, a):
    t = THEMES[name]
    costs = ue.monthly_costs(a, "standard")
    mid = ue.scenario_at(a, ue.MID, costs)
    fig, (left, right) = plt.subplots(1, 2, figsize=(10, 3.8), facecolor=t["surface"],
                                      gridspec_kw={"width_ratios": [1.4, 1]})

    installs = list(range(1, 151))
    net = [ue.monthly_net_eur(replace(mid, installs_per_day=i), 12) for i in installs]
    break_even = ue.break_even_installs(mid)
    left.plot(installs, net, color=t["series"], linewidth=2)
    left.axhline(0, color=t["base"], linewidth=1)
    left.plot([break_even], [0], "o", color=t["series"], markersize=8, markeredgecolor=t["surface"], markeredgewidth=2)
    left.annotate(f"Break-even: ~{break_even:.0f} installs/day", (break_even, 0), xytext=(break_even + 12, -75),
                  color=t["ink"], fontsize=10)
    left.set_ylim(-150, None)
    left.set_title("Monthly net result after a year (EUR)", color=t["ink"], fontsize=11, loc="left")
    left.set_xlabel("Organic installs per day", color=t["ink2"], fontsize=9)
    style(left, t)

    labels, values = [], []
    for label, level in ue.LEVELS:
        labels.append(label)
        values.append(ue.lifetime_value_eur(ue.scenario_at(a, level, costs)))
    cpi = ue.paid_cpi_eur(a)
    right.bar(labels, values, width=0.5, color=t["series"])
    right.axhline(cpi, color=t["ref"], linewidth=2, linestyle="--")
    right.text(2.3, cpi + 0.07, f"Cost of a paid install: EUR {cpi:.2f}", color=t["ink"], fontsize=10, ha="right")
    for x, v in enumerate(values):
        right.text(x, v + 0.04, f"EUR {v:.2f}", color=t["ink"], fontsize=10, ha="center")
    right.set_ylim(0, cpi * 1.3)
    right.set_title("Revenue per install, first year (EUR)", color=t["ink"], fontsize=11, loc="left")
    style(right, t)
    right.tick_params(axis="x", colors=t["ink2"], labelsize=10)

    fig.suptitle("Cheap to sustain, too expensive to buy users for", color=t["ink"], fontsize=13, x=0.01, ha="left")
    fig.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / f"unit_economics_{name}.png", dpi=160, facecolor=t["surface"])
    plt.close(fig)


if __name__ == "__main__":
    assumptions = ue.load_assumptions()
    for theme in THEMES:
        draw(theme, assumptions)
