"""Generate publication figures from committed, frozen aggregate artifacts only."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch

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
    fig, ax = plt.subplots(figsize=(11.6, 3.1))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 3.2)
    ax.axis("off")

    stages = [
        {
            "x": 1.45,
            "eyebrow": "INPUT HISTORY",
            "title": "Past-only normalization",
            "detail": "63 prior eligible sessions",
            "time": "history < t",
            "face": "#F3F2FF",
            "edge": BLUE,
        },
        {
            "x": 4.55,
            "eyebrow": "INFORMATION SET",
            "title": "Event bar closes",
            "detail": "Features locked; forecast formed",
            "time": "close t",
            "face": "#F3F2FF",
            "edge": BLUE,
        },
        {
            "x": 7.55,
            "eyebrow": "EXECUTION",
            "title": "First tradable open",
            "detail": "Return measurement begins",
            "time": "open t+1",
            "face": "#ECFAF5",
            "edge": GREEN,
        },
        {
            "x": 10.55,
            "eyebrow": "EVALUATION",
            "title": "Outcome measured",
            "detail": "5 min primary; 15/30/60 secondary",
            "time": "open t+h",
            "face": "#F5F5F5",
            "edge": GRAY,
        },
    ]

    line_y = 0.82
    ax.annotate(
        "",
        xy=(11.35, line_y),
        xytext=(0.65, line_y),
        arrowprops={"arrowstyle": "-|>", "color": "#8A8A8A", "lw": 1.15},
    )
    ax.axvline(
        stages[1]["x"],
        ymin=0.17,
        ymax=0.94,
        color=RED,
        linewidth=0.85,
        linestyle=(0, (3, 3)),
        zorder=0,
    )
    ax.text(
        stages[1]["x"],
        3.05,
        "INFORMATION CUTOFF",
        ha="center",
        va="top",
        fontsize=7.2,
        color=RED,
        fontweight="bold",
    )

    for stage in stages:
        x = stage["x"]
        box = FancyBboxPatch(
            (x - 1.33, 1.36),
            2.66,
            1.13,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            linewidth=0.85,
            edgecolor=stage["edge"],
            facecolor=stage["face"],
        )
        ax.add_patch(box)
        ax.text(
            x,
            2.29,
            stage["eyebrow"],
            ha="center",
            va="center",
            fontsize=7.0,
            color=stage["edge"],
            fontweight="bold",
        )
        ax.text(
            x,
            1.95,
            stage["title"],
            ha="center",
            va="center",
            fontsize=9.0,
            color=BLACK,
            fontweight="bold",
        )
        ax.text(
            x,
            1.64,
            stage["detail"],
            ha="center",
            va="center",
            fontsize=7.2,
            color=GRAY,
        )
        ax.scatter(
            [x],
            [line_y],
            s=42,
            color=stage["edge"],
            edgecolor="white",
            linewidth=1.0,
            zorder=3,
        )
        ax.text(
            x,
            0.46,
            stage["time"],
            ha="center",
            va="center",
            fontsize=7.5,
            color=BLACK,
        )

    ax.text(
        6,
        0.08,
        "All predictors are fixed before the first executable return is observed.",
        ha="center",
        va="bottom",
        fontsize=7.4,
        color=GRAY,
    )
    svg_output = FIGURES / "research_design.svg"
    fig.savefig(svg_output, format="svg", bbox_inches="tight", metadata={"Date": None})
    plt.close(fig)
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
