#!/usr/bin/env python3
"""Regenerate the selected figures from public aggregate CSV files."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
import numpy as np

# Select the non-interactive backend before importing pyplot.
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

from alpha_research.visualization import (  # noqa: E402
    BASELINE_COLOR,
    CANDIDATE_COLOR,
    plot_bootstrap_sharpe_difference,
    plot_cost_frontier,
    plot_drawdown_comparison,
    plot_net_nav,
    plot_walk_forward_folds,
)


LABELS = {
    "UBL_ONLY": "UBL only",
    "UBL_80_LOWVOL_60_20": "80% UBL / 20% LOWVOL",
    "ubl_net_return": "UBL only",
    "selected_net_return": "80% UBL / 20% LOWVOL",
}
PORTFOLIO_ORDER = ["UBL_ONLY", "UBL_80_LOWVOL_60_20"]
COLOR_MAP = {
    "UBL_ONLY": BASELINE_COLOR,
    "UBL_80_LOWVOL_60_20": CANDIDATE_COLOR,
}


def save(figure, path: Path) -> None:
    """Save and close one publication figure."""
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def annualized_sharpe(returns: pd.Series) -> float:
    """Return annualized Sharpe using a 0% cash hurdle."""
    clean = returns.dropna().astype(float)
    volatility = clean.std(ddof=1)
    if len(clean) < 2 or volatility == 0:
        raise ValueError("Sharpe requires at least two non-constant returns")
    return float(np.sqrt(252.0) * clean.mean() / volatility)


def plot_result_dashboard(
    returns: pd.DataFrame,
    headline_metrics: pd.DataFrame,
):
    """Summarize the observed holdout without obscuring its research status."""
    holdout_returns = returns[returns["split"] == "research_holdout"]
    if len(holdout_returns) != 133:
        raise ValueError(
            "result dashboard expects 133 observed holdout return rows; "
            f"found {len(holdout_returns)}"
        )

    holdout_metrics = headline_metrics[
        headline_metrics["split"] == "research_holdout"
    ].set_index("track")
    baseline = holdout_metrics.loc["UBL_ONLY"]
    selected = holdout_metrics.loc["UBL_80_LOWVOL_60_20"]

    gross_sharpe = [
        annualized_sharpe(
            holdout_returns["ubl_net_return"]
            + holdout_returns["ubl_transaction_cost"]
        ),
        annualized_sharpe(
            holdout_returns["selected_net_return"]
            + holdout_returns["selected_transaction_cost"]
        ),
    ]
    net_sharpe = [
        float(baseline["net_sharpe_0rf"]),
        float(selected["net_sharpe_0rf"]),
    ]

    figure = plt.figure(figsize=(13.2, 6.2))
    grid = figure.add_gridspec(
        1,
        2,
        width_ratios=[0.88, 1.35],
        left=0.06,
        right=0.97,
        top=0.78,
        bottom=0.21,
        wspace=0.18,
    )
    bar_axis = figure.add_subplot(grid[0, 0])
    card_axis = figure.add_subplot(grid[0, 1])

    figure.suptitle(
        "Observed Holdout: UBL + LOWVOL versus UBL",
        x=0.06,
        y=0.96,
        ha="left",
        fontsize=18,
        fontweight="bold",
        color="#111827",
    )
    figure.text(
        0.06,
        0.885,
        "Risk-adjusted improvement after security-level turnover netting "
        "and transaction costs",
        ha="left",
        fontsize=11,
        color="#4B5563",
    )

    categories = ["Gross", "Net after 10 bps"]
    positions = np.arange(len(categories))
    width = 0.34
    baseline_bars = bar_axis.bar(
        positions - width / 2,
        [gross_sharpe[0], net_sharpe[0]],
        width,
        color=BASELINE_COLOR,
        label="UBL only",
    )
    selected_bars = bar_axis.bar(
        positions + width / 2,
        [gross_sharpe[1], net_sharpe[1]],
        width,
        color=CANDIDATE_COLOR,
        label="80% UBL / 20% LOWVOL",
    )
    bar_axis.bar_label(baseline_bars, fmt="%.2f", padding=3, fontsize=10)
    bar_axis.bar_label(selected_bars, fmt="%.2f", padding=3, fontsize=10)
    bar_axis.set_title(
        "Annualized Sharpe, 0% cash hurdle",
        loc="left",
        fontsize=12,
        fontweight="bold",
    )
    bar_axis.set_xticks(positions, categories)
    bar_axis.set_ylim(0, 3.55)
    bar_axis.grid(axis="y", color="#D1D5DB", linewidth=0.7, alpha=0.65)
    bar_axis.set_axisbelow(True)
    bar_axis.spines[["top", "right", "left"]].set_visible(False)
    bar_axis.tick_params(axis="y", left=False, labelleft=False)
    bar_axis.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=2, fontsize=9)

    card_axis.axis("off")
    card_specs = [
        (
            "Net return",
            f"{baseline['net_total_return']:.2%}",
            f"{selected['net_total_return']:.2%}",
            f"+{(selected['net_total_return'] - baseline['net_total_return']) * 100:.2f} pp",
        ),
        (
            "Maximum drawdown",
            f"{baseline['net_max_drawdown']:.2%}",
            f"{selected['net_max_drawdown']:.2%}",
            f"{(selected['net_max_drawdown'] / baseline['net_max_drawdown'] - 1):.1%}",
        ),
        (
            "Average full turnover",
            f"{baseline['average_full_turnover']:.3f}",
            f"{selected['average_full_turnover']:.3f}",
            f"{(selected['average_full_turnover'] / baseline['average_full_turnover'] - 1):.1%}",
        ),
        (
            "Break-even cost",
            f"{baseline['break_even_cost_bps']:.2f} bps",
            f"{selected['break_even_cost_bps']:.2f} bps",
            f"+{selected['break_even_cost_bps'] - baseline['break_even_cost_bps']:.2f} bps",
        ),
    ]
    for index, (title, before, after, change) in enumerate(card_specs):
        row, column = divmod(index, 2)
        x = 0.02 + column * 0.50
        y = 0.54 - row * 0.51
        patch = FancyBboxPatch(
            (x, y),
            0.46,
            0.40,
            boxstyle="round,pad=0.012,rounding_size=0.018",
            transform=card_axis.transAxes,
            facecolor="#F8FAFC",
            edgecolor="#D1D5DB",
            linewidth=1.0,
        )
        card_axis.add_patch(patch)
        card_axis.text(
            x + 0.03,
            y + 0.31,
            title,
            transform=card_axis.transAxes,
            fontsize=10,
            fontweight="bold",
            color="#374151",
        )
        card_axis.text(
            x + 0.03,
            y + 0.18,
            f"{before}  $\\rightarrow$  {after}",
            transform=card_axis.transAxes,
            fontsize=13,
            fontweight="bold",
            color="#111827",
        )
        card_axis.text(
            x + 0.03,
            y + 0.07,
            change,
            transform=card_axis.transAxes,
            fontsize=10,
            color=CANDIDATE_COLOR,
        )

    figure.text(
        0.06,
        0.045,
        "133 daily observations | gross exposure 2 | next-tradable VWAP | "
        "10 bps per dollar traded | holdout viewed",
        ha="left",
        fontsize=9,
        color="#4B5563",
    )
    return figure


def render(root: Path) -> list[Path]:
    """Render all public figures from the aggregate evidence under ``root``."""
    data = root / "data"
    plots = root / "plots"
    returns = pd.read_csv(data / "portfolio_returns.csv", parse_dates=["date"])
    returns = returns.sort_values("date").set_index("date")
    return_frame = returns[["ubl_net_return", "selected_net_return"]]
    headline_metrics = pd.read_csv(data / "headline_metrics.csv")
    split_starts = {
        split.replace("research_", "").title(): group.index.min()
        for split, group in returns.groupby("split")
        if split != "train"
    }
    outputs = []
    figure = plot_result_dashboard(returns.reset_index(), headline_metrics)
    outputs.append(plots / "00_result_at_a_glance.png")
    save(figure, outputs[-1])

    figure = plot_net_nav(return_frame, labels=LABELS, split_starts=split_starts)
    figure.axes[0].set_title(
        "Net NAV at 10 bps per dollar traded",
        loc="left",
        fontsize=13,
        fontweight="bold",
    )
    outputs.append(plots / "01_net_nav_comparison.png")
    save(figure, outputs[-1])

    figure = plot_drawdown_comparison(return_frame, labels=LABELS)
    figure.axes[0].set_title(
        "Net drawdown at 10 bps per dollar traded",
        loc="left",
        fontsize=13,
        fontweight="bold",
    )
    outputs.append(plots / "02_drawdown_comparison.png")
    save(figure, outputs[-1])

    costs = pd.read_csv(data / "cost_sensitivity.csv")
    figure = plot_cost_frontier(
        costs,
        labels=LABELS,
        portfolio_order=PORTFOLIO_ORDER,
        color_map=COLOR_MAP,
    )
    figure.axes[0].set_title(
        "Transaction-cost frontier (full common sample)",
        loc="left",
        fontsize=13,
        fontweight="bold",
    )
    cost_axis = figure.axes[0]
    cost_axis.axvspan(10.0, 15.0, color="#F3F4F6", alpha=0.55, zorder=0)
    cost_axis.axvline(
        10.0,
        color="#6B7280",
        linestyle="--",
        linewidth=1.0,
    )
    cost_axis.text(
        10.25,
        cost_axis.get_ylim()[1] * 0.92,
        "Base cost",
        color="#4B5563",
        fontsize=9,
    )
    all_metrics = headline_metrics[headline_metrics["split"] == "all"].set_index(
        "track"
    )
    for portfolio in PORTFOLIO_ORDER:
        row = costs[
            (costs["portfolio"] == portfolio) & (costs["cost_bps"] == 15)
        ].iloc[0]
        color = COLOR_MAP[portfolio]
        cost_axis.annotate(
            f"{row['net_sharpe_0rf']:.2f} at 15 bps",
            xy=(15, row["net_sharpe_0rf"]),
            xytext=((7, 8) if portfolio == "UBL_80_LOWVOL_60_20" else (-75, 10)),
            textcoords="offset points",
            color=color,
            fontsize=9,
        )
        break_even = float(all_metrics.loc[portfolio, "break_even_cost_bps"])
        cost_axis.scatter(
            [break_even],
            [0],
            marker="D",
            s=34,
            color=color,
            zorder=4,
        )
        cost_axis.annotate(
            f"BE {break_even:.1f}",
            xy=(break_even, 0),
            xytext=(4, 8 if portfolio == "UBL_80_LOWVOL_60_20" else -16),
            textcoords="offset points",
            color=color,
            fontsize=8,
        )
    outputs.append(plots / "03_transaction_cost_frontier.png")
    save(figure, outputs[-1])

    bootstrap = pd.read_csv(data / "bootstrap_sharpe_differences.csv")
    figure = plot_bootstrap_sharpe_difference(
        bootstrap["sharpe_difference"],
        difference_label=(
            "Sharpe(80% UBL / 20% LOWVOL) - Sharpe(UBL only)"
        ),
    )
    figure.axes[0].set_title(
        "Holdout paired bootstrap: Sharpe difference",
        loc="left",
        fontsize=13,
        fontweight="bold",
    )
    positive_fraction = (bootstrap["sharpe_difference"] > 0).mean()
    figure.axes[0].text(
        0.98,
        0.92,
        f"{positive_fraction:.1%} of paired resamples\n"
        "have Sharpe difference > 0",
        transform=figure.axes[0].transAxes,
        ha="right",
        va="top",
        fontsize=10,
        fontweight="bold",
        color="#111827",
        bbox={
            "boxstyle": "round,pad=0.35",
            "facecolor": "white",
            "edgecolor": "#D1D5DB",
            "alpha": 0.92,
        },
    )
    outputs.append(plots / "04_paired_bootstrap_sharpe_difference.png")
    save(figure, outputs[-1])

    folds = pd.read_csv(data / "walk_forward_folds.csv")
    figure = plot_walk_forward_folds(
        folds,
        labels=LABELS,
        portfolio_order=PORTFOLIO_ORDER,
        color_map=COLOR_MAP,
    )
    outputs.append(plots / "05_walk_forward_fold_returns.png")
    save(figure, outputs[-1])

    concentration = pd.read_csv(data / "pnl_concentration.csv")
    fig, ax = plt.subplots(figsize=(7.4, 4.8))
    values = (
        concentration.set_index("portfolio").reindex(PORTFOLIO_ORDER)[
            "top_five_day_pnl_share"
        ]
        * 100.0
    )
    labels = [LABELS.get(name, name) for name in values.index]
    bars = ax.bar(labels, values, color=[BASELINE_COLOR, CANDIDATE_COLOR], width=0.58)
    ax.bar_label(bars, fmt="%.1f%%", padding=3)
    ax.set_title(
        "Top-five-day PnL concentration", loc="left", fontsize=13, fontweight="bold"
    )
    ax.set_ylabel("Share of full-sample arithmetic net PnL (%)")
    ax.grid(axis="y", color="#D1D5DB", linewidth=0.7, alpha=0.65)
    ax.spines[["top", "right"]].set_visible(False)
    outputs.append(plots / "06_pnl_concentration.png")
    save(fig, outputs[-1])
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("examples/sample_outputs/ubl_lowvol_study"),
    )
    args = parser.parse_args()
    for path in render(args.root):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
