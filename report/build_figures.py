"""Generate publication figures from committed, frozen aggregate artifacts only."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports" / "development"
FIGURES = ROOT / "report" / "figures"

BLUE = "#6C63FF"
GREEN = "#00A878"
RED = "#D95F59"
GRAY = "#525252"
BLACK = "#1A1A1A"
GRID = "#D9D9D9"


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 7.5,
            "axes.titlesize": 8.5,
            "axes.titleweight": "normal",
            "axes.labelsize": 8,
            "axes.edgecolor": BLACK,
            "axes.linewidth": 0.6,
            "axes.spines.top": True,
            "axes.spines.right": True,
            "xtick.color": BLACK,
            "ytick.color": BLACK,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "xtick.major.size": 3,
            "ytick.major.size": 3,
            "axes.labelcolor": BLACK,
            "text.color": BLACK,
            "grid.color": GRID,
            "grid.linewidth": 0.55,
            "grid.alpha": 0.8,
            "legend.fontsize": 7,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "svg.fonttype": "none",
            "svg.hashsalt": "btc-nq-coherence-research",
        }
    )


def build_research_design() -> Path:
    """Build the causal-timing diagram used by the public README."""
    fig, ax = plt.subplots(figsize=(10.8, 2.65))
    ax.set_xlim(0, 10.8)
    ax.set_ylim(0, 2.8)
    ax.axis("off")

    history_start = 0.75
    event_close = 4.45
    tradable_open = 6.55
    outcome_open = 9.75
    line_y = 1.18

    ax.add_patch(
        Rectangle(
            (history_start, line_y - 0.11),
            event_close - history_start,
            0.22,
            facecolor="#E8E8E8",
            edgecolor="none",
            zorder=1,
        )
    )
    ax.add_patch(
        Rectangle(
            (tradable_open, line_y - 0.11),
            outcome_open - tradable_open,
            0.22,
            facecolor="#CFCFCF",
            edgecolor="none",
            zorder=1,
        )
    )
    ax.annotate(
        "",
        xy=(10.25, line_y),
        xytext=(0.55, line_y),
        arrowprops={"arrowstyle": "-|>", "color": "#5A5A5A", "lw": 0.9},
    )
    ax.axvline(
        event_close,
        ymin=0.16,
        ymax=0.90,
        color=BLACK,
        linewidth=0.7,
        linestyle=(0, (2.5, 2.5)),
        zorder=0,
    )

    ax.text(
        (history_start + event_close) / 2,
        line_y,
        "historical feature construction",
        ha="center",
        va="center",
        fontsize=7.1,
        color=BLACK,
    )
    ax.text(
        (tradable_open + outcome_open) / 2,
        line_y,
        "return measurement window",
        ha="center",
        va="center",
        fontsize=7.1,
        color=BLACK,
    )
    ax.text(
        (event_close + tradable_open) / 2,
        line_y + 0.20,
        "no close-price fill",
        ha="center",
        va="bottom",
        fontsize=6.8,
        color=GRAY,
    )

    markers = [history_start, event_close, tradable_open, outcome_open]
    ax.scatter(
        markers,
        [line_y] * len(markers),
        s=20,
        facecolor="white",
        edgecolor=BLACK,
        linewidth=0.8,
        zorder=3,
    )

    annotations = [
        (
            history_start,
            2.20,
            "Prior eligible sessions",
            "same-slot scale; causal lookbacks",
            "history < t",
        ),
        (
            event_close,
            2.20,
            "Event bar closes",
            "features locked; forecast formed",
            "close t",
        ),
        (
            tradable_open,
            0.63,
            "First tradable open",
            "return measurement begins",
            "open t+1",
        ),
        (
            outcome_open,
            2.20,
            "Outcome measured",
            "5 min primary; 15/30/60 min secondary",
            "open t+h",
        ),
    ]
    for x, title_y, title, detail, time in annotations:
        above_axis = title_y > line_y
        end_y = title_y - 0.18 if above_axis else title_y + 0.18
        ax.plot(
            [x, x],
            [line_y + (0.11 if above_axis else -0.11), end_y],
            color="#777777",
            linewidth=0.55,
            zorder=0,
        )
        ax.text(
            x,
            title_y,
            title,
            ha="center",
            va="center",
            fontsize=8.0,
            color=BLACK,
            fontweight="bold",
        )
        ax.text(
            x,
            title_y - 0.28,
            detail,
            ha="center",
            va="center",
            fontsize=6.8,
            color=GRAY,
        )
        ax.text(
            x,
            title_y + 0.27 if above_axis else title_y - 0.55,
            time,
            ha="center",
            va="center",
            fontsize=6.8,
            color=BLACK,
        )

    ax.text(
        event_close,
        0.30,
        "information cutoff",
        ha="center",
        va="center",
        fontsize=6.4,
        color=BLACK,
        fontstyle="italic",
    )
    svg_output = FIGURES / "research_design.svg"
    fig.savefig(svg_output, format="svg", bbox_inches="tight", metadata={"Date": None})
    plt.close(fig)
    normalized_svg = "\n".join(
        line.rstrip() for line in svg_output.read_text(encoding="utf-8").splitlines()
    )
    svg_output.write_text(normalized_svg + "\n", encoding="utf-8", newline="\n")
    return svg_output


def _errorbar_panel(
    ax: Any,
    estimates: list[float],
    intervals: list[list[float]],
    labels: list[str],
    title: str,
    xlabel: str,
    scale: float = 1.0,
) -> None:
    y = np.arange(len(labels))[::-1]
    values = np.asarray(estimates) * scale
    lower = np.asarray([value[0] for value in intervals]) * scale
    upper = np.asarray([value[1] for value in intervals]) * scale
    errors = np.vstack([values - lower, upper - values])
    colors = [BLUE, GREEN]
    for index, color in enumerate(colors):
        ax.errorbar(
            values[index],
            y[index],
            xerr=errors[:, index].reshape(2, 1),
            fmt="o",
            color=color,
            ecolor=color,
            markersize=4,
            markeredgecolor=BLACK,
            markeredgewidth=0.35,
            elinewidth=1.0,
            capsize=3,
            capthick=0.8,
            zorder=3,
        )
    ax.axvline(0, color=RED, linestyle="--", linewidth=0.8)
    ax.set_yticks(y, labels)
    ax.set_title(title, loc="left", pad=7)
    ax.set_xlabel(xlabel)
    ax.grid(axis="x")


def build_primary_results(
    state: dict[str, Any], returns: dict[str, Any], overnight: dict[str, Any]
) -> Path:
    cash_state = state["five_minute_primary"]["m1_minus_m0"]
    overnight_state = overnight["state_model"]["five_minute_primary"]["m1_minus_m0"]
    cash_return = returns["five_minute_primary"]["cross_market_minus_nq_only"]
    overnight_return = overnight["return_model"]["five_minute_primary"][
        "cross_market_minus_nq_only"
    ]

    fig, axes = plt.subplots(1, 2, figsize=(9.2, 2.75), constrained_layout=True)
    _errorbar_panel(
        axes[0],
        [
            cash_state["brier_score_difference"],
            overnight_state["brier_score_difference"],
        ],
        [
            cash_state["brier_session_block_95_ci"],
            overnight_state["brier_session_block_95_ci"],
        ],
        ["Cash session", "Overnight control"],
        r"A. State persistence: $M_1-M_0$",
        r"Brier-loss difference ($\times 10^{-4}$)",
        scale=10_000,
    )
    _errorbar_panel(
        axes[1],
        [
            cash_return["mean_squared_error_difference"],
            overnight_return["mean_squared_error_difference"],
        ],
        [
            cash_return["squared_error_session_block_95_ci"],
            overnight_return["squared_error_session_block_95_ci"],
        ],
        ["Cash session", "Overnight control"],
        r"B. NQ return forecast: cross-market $-$ NQ-only",
        r"MSE difference ($\mathrm{bps}^2$)",
    )
    output = FIGURES / "primary_results.png"
    fig.savefig(output, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return output


def _response_rows(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    return frame.loc[
        frame["resolution_minutes"].eq(5)
        & frame["direction"].eq("all")
        & frame["horizon_minutes"].isin([5, 15, 30, 60])
    ].sort_values("horizon_minutes")


def build_response_curve() -> Path:
    cash = _response_rows(REPORTS / "horizon_response.csv")
    overnight = _response_rows(REPORTS / "overnight_horizon_response.csv")
    fig, ax = plt.subplots(figsize=(7.3, 3.0), constrained_layout=True)
    x = np.arange(4)
    for offset, frame, label, color in [
        (-0.07, cash, "Cash session", BLUE),
        (0.07, overnight, "Overnight control", GREEN),
    ]:
        mean = frame["mean_signed_nq_return_bps"].to_numpy()
        lo = frame["block_bootstrap_ci_lower_bps"].to_numpy()
        hi = frame["block_bootstrap_ci_upper_bps"].to_numpy()
        ax.errorbar(
            x + offset,
            mean,
            yerr=np.vstack([mean - lo, hi - mean]),
            marker="o",
            markersize=3.8,
            markeredgecolor=BLACK,
            markeredgewidth=0.3,
            linewidth=1.1,
            elinewidth=0.9,
            capsize=2.5,
            color=color,
            label=label,
        )
    ax.axhline(0, color=RED, linestyle="--", linewidth=0.8)
    ax.set_xticks(x, ["5 (primary)", "15", "30", "60"])
    ax.set_xlabel("Forward horizon (minutes)")
    ax.set_ylabel("Mean signed NQ return (bps)")
    ax.grid()
    ax.legend(frameon=False, ncol=2, loc="upper left")
    output = FIGURES / "response_curve.png"
    fig.savefig(output, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return output


def _calibration_rows(path: Path, model: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    return frame.loc[
        frame["resolution_minutes"].eq(5)
        & frame["model"].eq(model)
        & frame["event_count"].gt(0)
    ].dropna(subset=["mean_predicted_probability", "observed_agreement_rate"])


def build_calibration() -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(8.0, 3.0), constrained_layout=True)
    for ax, path, title in [
        (axes[0], REPORTS / "state_model_calibration.csv", "Cash session"),
        (axes[1], REPORTS / "overnight_state_calibration.csv", "Overnight control"),
    ]:
        for model, label, color, marker in [
            ("m0", r"$M_0$: coherence", BLUE, "o"),
            ("m1", r"$M_1$: + magnitude", GREEN, "s"),
        ]:
            frame = _calibration_rows(path, model)
            ax.plot(
                frame["mean_predicted_probability"],
                frame["observed_agreement_rate"],
                marker=marker,
                markersize=3.8,
                markeredgecolor=BLACK,
                markeredgewidth=0.3,
                linewidth=1.0,
                color=color,
                label=label,
            )
        ax.plot([0.45, 0.85], [0.45, 0.85], color=RED, linestyle="--", linewidth=0.8)
        ax.set_xlim(0.45, 0.85)
        ax.set_ylim(0.40, 0.85)
        ax.set_title(title, loc="left")
        ax.set_xlabel("Mean predicted probability")
        ax.grid()
    axes[0].set_ylabel("Observed agreement rate")
    axes[1].legend(frameon=False, loc="lower right", fontsize=8)
    output = FIGURES / "state_calibration.png"
    fig.savefig(output, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return output


def build_all() -> dict[str, Any]:
    """Build every report figure and return its reproducibility manifest."""
    _style()
    FIGURES.mkdir(parents=True, exist_ok=True)
    inputs = {
        "state_model_summary.json": REPORTS / "state_model_summary.json",
        "return_model_summary.json": REPORTS / "return_model_summary.json",
        "overnight_control_summary.json": REPORTS / "overnight_control_summary.json",
        "horizon_response.csv": REPORTS / "horizon_response.csv",
        "overnight_horizon_response.csv": REPORTS / "overnight_horizon_response.csv",
        "state_model_calibration.csv": REPORTS / "state_model_calibration.csv",
        "overnight_state_calibration.csv": REPORTS / "overnight_state_calibration.csv",
    }
    state = _load_json(inputs["state_model_summary.json"])
    returns = _load_json(inputs["return_model_summary.json"])
    overnight = _load_json(inputs["overnight_control_summary.json"])
    outputs = [
        build_research_design(),
        build_primary_results(state, returns, overnight),
        build_response_curve(),
        build_calibration(),
    ]
    manifest = {
        "schema_version": 1,
        "source_policy": "committed_frozen_aggregates_only",
        "inputs": {name: _hash(path) for name, path in inputs.items()},
        "figures": {path.name: _hash(path) for path in outputs},
    }
    manifest_path = ROOT / "report" / "figure_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


if __name__ == "__main__":
    result = build_all()
    print(f"Built {len(result['figures'])} frozen-data report figures.")
