"""Generate publication figures from committed, frozen aggregate artifacts only."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports" / "development"
FIGURES = ROOT / "report" / "figures"

NAVY = "#17324D"
BLUE = "#2F5D8A"
TEAL = "#3B7A78"
RED = "#A64B4B"
GRAY = "#667085"
LIGHT = "#D8E1E8"


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
            "font.size": 9,
            "axes.titlesize": 10.5,
            "axes.titleweight": "bold",
            "axes.labelsize": 9,
            "axes.edgecolor": LIGHT,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "xtick.color": GRAY,
            "ytick.color": NAVY,
            "axes.labelcolor": NAVY,
            "text.color": NAVY,
            "grid.color": "#E8EDF1",
            "grid.linewidth": 0.7,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


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
    colors = [TEAL, BLUE]
    ax.errorbar(
        values,
        y,
        xerr=errors,
        fmt="none",
        ecolor=GRAY,
        elinewidth=2,
        capsize=4,
        capthick=1.3,
        zorder=2,
    )
    ax.scatter(values, y, s=48, c=colors, edgecolor="white", linewidth=0.8, zorder=3)
    ax.axvline(0, color=RED, linestyle="--", linewidth=1)
    ax.set_yticks(y, labels)
    ax.set_title(title, loc="left", pad=10)
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

    fig, axes = plt.subplots(1, 2, figsize=(10.6, 3.15), constrained_layout=True)
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
        "A. State persistence: M1 minus M0",
        "Brier-loss difference (x10^-4)",
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
        "B. NQ return forecast: cross-market minus NQ-only",
        "MSE difference (bps^2)",
    )
    fig.suptitle(
        "Cross-market magnitude improves state prediction, not the primary return forecast",
        x=0.01,
        ha="left",
        fontsize=12,
        fontweight="bold",
        color=NAVY,
    )
    output = FIGURES / "primary_results.png"
    fig.savefig(output, dpi=220, bbox_inches="tight")
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
    fig, ax = plt.subplots(figsize=(7.9, 3.25), constrained_layout=True)
    x = np.arange(4)
    for offset, frame, label, color in [
        (-0.07, cash, "Cash session", NAVY),
        (0.07, overnight, "Overnight control", TEAL),
    ]:
        mean = frame["mean_signed_nq_return_bps"].to_numpy()
        lo = frame["block_bootstrap_ci_lower_bps"].to_numpy()
        hi = frame["block_bootstrap_ci_upper_bps"].to_numpy()
        ax.errorbar(
            x + offset,
            mean,
            yerr=np.vstack([mean - lo, hi - mean]),
            marker="o",
            markersize=5,
            linewidth=1.7,
            capsize=3,
            color=color,
            label=label,
        )
    ax.axhline(0, color=RED, linestyle="--", linewidth=1)
    ax.set_xticks(x, ["5 (primary)", "15", "30", "60"])
    ax.set_xlabel("Forward horizon (minutes)")
    ax.set_ylabel("Mean signed NQ return (bps)")
    ax.set_title("Prespecified response curve with session-block 95% intervals", loc="left")
    ax.grid(axis="y")
    ax.legend(frameon=False, ncol=2, loc="upper left")
    output = FIGURES / "response_curve.png"
    fig.savefig(output, dpi=220, bbox_inches="tight")
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
    fig, axes = plt.subplots(1, 2, figsize=(8.5, 3.25), constrained_layout=True)
    for ax, path, title in [
        (axes[0], REPORTS / "state_model_calibration.csv", "Cash session"),
        (axes[1], REPORTS / "overnight_state_calibration.csv", "Overnight control"),
    ]:
        for model, label, color, marker in [
            ("m0", "M0: coherence", GRAY, "o"),
            ("m1", "M1: + magnitude", TEAL, "s"),
        ]:
            frame = _calibration_rows(path, model)
            ax.plot(
                frame["mean_predicted_probability"],
                frame["observed_agreement_rate"],
                marker=marker,
                markersize=5,
                linewidth=1.5,
                color=color,
                label=label,
            )
        ax.plot([0, 1], [0, 1], color=RED, linestyle="--", linewidth=1)
        ax.set_xlim(0.45, 0.85)
        ax.set_ylim(0.45, 0.85)
        ax.set_title(title, loc="left")
        ax.set_xlabel("Mean predicted probability")
        ax.grid()
    axes[0].set_ylabel("Observed agreement rate")
    axes[1].legend(frameon=False, loc="lower right", fontsize=8)
    fig.suptitle(
        "Five-minute state-model reliability",
        x=0.01,
        ha="left",
        fontsize=11.5,
        fontweight="bold",
    )
    output = FIGURES / "state_calibration.png"
    fig.savefig(output, dpi=220, bbox_inches="tight")
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
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


if __name__ == "__main__":
    result = build_all()
    print(f"Built {len(result['figures'])} frozen-data report figures.")
