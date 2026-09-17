"""Development-only descriptive response surfaces and horizon curves."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]
import yaml


class DescriptiveError(ValueError):
    """Raised when descriptive analysis differs from the registered design."""


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        payload = yaml.safe_load(stream)
    if not isinstance(payload, dict):
        raise DescriptiveError(f"YAML root must be a mapping: {path}")
    return payload


def validate_descriptive_config(config: dict[str, Any]) -> None:
    """Keep the descriptive analysis independent of observed outcomes."""
    if config.get("schema_version") != 1 or config.get("status") != "development_only":
        raise DescriptiveError("Descriptive config must remain schema 1 and development-only.")
    population = config.get("population", {})
    if population != {"feature_ready": True, "current_direction_agreement": 1}:
        raise DescriptiveError("Population must be feature-ready current-agreement events.")
    surface = config.get("response_surface", {})
    expected_surface = {
        "resolution_minutes": 5,
        "feature_bins": 5,
        "bin_method": "feature_only_empirical_quantiles",
        "dimensions": ["joint_intensity", "magnitude_balance"],
        "primary_outcome": "signed_nq_return_bps_5m",
        "low_count_threshold": 30,
        "low_count_policy": "flag_not_filter",
    }
    if surface != expected_surface:
        raise DescriptiveError("Response-surface specification has drifted.")
    horizons = config.get("horizon_response", {})
    if horizons.get("five_minute_minutes") != [5, 15, 30, 60]:
        raise DescriptiveError("Five-minute response curve must remain 5/15/30/60.")
    if horizons.get("one_minute_minutes") != [1, 2, 3, 4, 5, 15, 30, 60]:
        raise DescriptiveError("One-minute response curve is not the registered path.")
    uncertainty = config.get("uncertainty", {})
    if uncertainty.get("method") != "analysis_session_block_bootstrap":
        raise DescriptiveError("Uncertainty must use analysis-session block bootstrap.")
    if uncertainty.get("confidence_level") != 0.95:
        raise DescriptiveError("Confidence level must remain 95%.")
    if int(uncertainty.get("replications", 0)) < 1000:
        raise DescriptiveError("At least 1,000 bootstrap replications are required.")


def load_outcomes(path: Path, expected_hash: str) -> pd.DataFrame:
    """Load a registered local outcome artifact."""
    if not path.is_file() or _hash_file(path) != expected_hash:
        raise DescriptiveError(f"Outcome artifact identity mismatch: {path}")
    frame = pd.read_csv(path)
    required = {
        "timestamp_utc",
        "analysis_session_date",
        "feature_ready",
        "direction_agreement",
        "common_direction",
        "joint_intensity",
        "magnitude_balance",
        "next_bar_agreement_label",
        "persistence_run_minutes",
        "persistence_end_observed",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise DescriptiveError(f"Outcome artifact is missing columns: {sorted(missing)}")
    frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True)
    frame = frame.set_index("timestamp_utc").sort_index()
    if frame.index.has_duplicates:
        raise DescriptiveError("Outcome timestamps must be unique.")
    return frame


def event_population(frame: pd.DataFrame) -> pd.DataFrame:
    """Select events using contemporaneous features only."""
    ready = frame["feature_ready"].astype(str).str.lower().eq("true")
    mask = (
        ready
        & frame["direction_agreement"].eq(1)
        & frame["common_direction"].isin([-1, 1])
        & frame["joint_intensity"].notna()
        & frame["magnitude_balance"].notna()
    )
    return frame.loc[mask].copy()


def feature_quantile_bins(
    events: pd.DataFrame, column: str, bin_count: int
) -> tuple[pd.Series, list[float]]:
    """Bin one feature without reading any outcome column."""
    quantiles = [index / bin_count for index in range(bin_count + 1)]
    edges = [float(events[column].quantile(value)) for value in quantiles]
    if len(set(edges)) != len(edges):
        raise DescriptiveError(f"Feature {column} does not have distinct quantile edges.")
    labels = list(range(1, bin_count + 1))
    assignments = pd.cut(
        events[column], bins=edges, labels=labels, include_lowest=True
    ).astype("Int64")
    return assignments, edges


def _percentile(sorted_values: list[float], probability: float) -> float:
    position = probability * (len(sorted_values) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def session_block_interval(
    frame: pd.DataFrame,
    value_column: str,
    *,
    replications: int,
    confidence_level: float,
    seed: int,
) -> tuple[float, float]:
    """Bootstrap whole sessions, retaining all overlapping observations within them."""
    valid = frame.loc[frame[value_column].notna(), ["analysis_session_date", value_column]]
    grouped = valid.groupby("analysis_session_date")[value_column].agg(["sum", "count"])
    clusters = [(float(row["sum"]), int(row["count"])) for _, row in grouped.iterrows()]
    if not clusters:
        return math.nan, math.nan
    rng = random.Random(seed)
    estimates: list[float] = []
    for _ in range(replications):
        selected = rng.choices(clusters, k=len(clusters))
        total_count = sum(count for _, count in selected)
        estimates.append(sum(total for total, _ in selected) / total_count)
    estimates.sort()
    tail = (1.0 - confidence_level) / 2.0
    return _percentile(estimates, tail), _percentile(estimates, 1.0 - tail)


def _optional_float(value: Any) -> float | None:
    if pd.isna(value):
        return None
    return float(value)


def response_surface(
    events: pd.DataFrame, *, bin_count: int, low_count_threshold: int
) -> tuple[pd.DataFrame, dict[str, list[float]]]:
    """Create a complete 5x5 feature surface overall and by common direction."""
    result = events.copy()
    result["joint_intensity_bin"], intensity_edges = feature_quantile_bins(
        result, "joint_intensity", bin_count
    )
    result["magnitude_balance_bin"], balance_edges = feature_quantile_bins(
        result, "magnitude_balance", bin_count
    )
    rows: list[dict[str, Any]] = []
    strata: list[tuple[str, pd.DataFrame]] = [
        ("all", result),
        ("up", result.loc[result["common_direction"].eq(1)]),
        ("down", result.loc[result["common_direction"].eq(-1)]),
    ]
    for direction, stratum in strata:
        for intensity_bin in range(1, bin_count + 1):
            for balance_bin in range(1, bin_count + 1):
                cell = stratum.loc[
                    stratum["joint_intensity_bin"].eq(intensity_bin)
                    & stratum["magnitude_balance_bin"].eq(balance_bin)
                ]
                primary = cell.loc[cell["signed_nq_return_bps_5m"].notna()]
                observed_duration = cell.loc[
                    cell["persistence_end_observed"].astype(str).str.lower().eq("true"),
                    "persistence_run_minutes",
                ]
                rows.append(
                    {
                        "direction": direction,
                        "joint_intensity_bin": intensity_bin,
                        "magnitude_balance_bin": balance_bin,
                        "event_count": int(len(primary)),
                        "session_count": int(
                            primary["analysis_session_date"].nunique()
                        ),
                        "mean_signed_nq_return_bps_5m": _optional_float(
                            primary["signed_nq_return_bps_5m"].mean()
                        ),
                        "median_signed_nq_return_bps_5m": _optional_float(
                            primary["signed_nq_return_bps_5m"].median()
                        ),
                        "mean_raw_nq_return_bps_5m": _optional_float(
                            primary["nq_return_bps_5m"].mean()
                        ),
                        "next_bar_agreement_probability": _optional_float(
                            cell["next_bar_agreement_label"].mean()
                        ),
                        "uncensored_persistence_count": int(len(observed_duration)),
                        "mean_uncensored_persistence_minutes": _optional_float(
                            observed_duration.mean()
                        ),
                        "low_count": len(primary) < low_count_threshold,
                    }
                )
    edges = {
        "joint_intensity": intensity_edges,
        "magnitude_balance": balance_edges,
    }
    return pd.DataFrame(rows), edges


def horizon_response(
    events: pd.DataFrame,
    *,
    resolution_minutes: int,
    horizons: list[int],
    replications: int,
    confidence_level: float,
    seed: int,
) -> pd.DataFrame:
    """Summarize prespecified horizons with session-block confidence intervals."""
    rows: list[dict[str, Any]] = []
    strata: list[tuple[str, pd.DataFrame]] = [
        ("all", events),
        ("up", events.loc[events["common_direction"].eq(1)]),
        ("down", events.loc[events["common_direction"].eq(-1)]),
    ]
    for stratum_number, (direction, stratum) in enumerate(strata):
        for horizon in horizons:
            value_column = f"signed_nq_return_bps_{horizon}m"
            valid = stratum.loc[stratum[value_column].notna()]
            interval_seed = seed + resolution_minutes * 10_000 + stratum_number * 100 + horizon
            lower, upper = session_block_interval(
                valid,
                value_column,
                replications=replications,
                confidence_level=confidence_level,
                seed=interval_seed,
            )
            rows.append(
                {
                    "resolution_minutes": resolution_minutes,
                    "direction": direction,
                    "horizon_minutes": horizon,
                    "event_count": int(len(valid)),
                    "session_count": int(valid["analysis_session_date"].nunique()),
                    "mean_signed_nq_return_bps": _optional_float(
                        valid[value_column].mean()
                    ),
                    "median_signed_nq_return_bps": _optional_float(
                        valid[value_column].median()
                    ),
                    "block_bootstrap_ci_lower_bps": _optional_float(lower),
                    "block_bootstrap_ci_upper_bps": _optional_float(upper),
                }
            )
    return pd.DataFrame(rows)


def weekday_diagnostics(events: pd.DataFrame) -> pd.DataFrame:
    """Expose the known weekday imbalance instead of averaging it away silently."""
    result = events.copy()
    result["weekday"] = pd.to_datetime(result["analysis_session_date"]).dt.day_name()
    rows: list[dict[str, Any]] = []
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    for weekday in order:
        subset = result.loc[
            result["weekday"].eq(weekday) & result["signed_nq_return_bps_5m"].notna()
        ]
        rows.append(
            {
                "weekday": weekday,
                "event_count": int(len(subset)),
                "session_count": int(subset["analysis_session_date"].nunique()),
                "mean_signed_nq_return_bps_5m": _optional_float(
                    subset["signed_nq_return_bps_5m"].mean()
                ),
                "median_signed_nq_return_bps_5m": _optional_float(
                    subset["signed_nq_return_bps_5m"].median()
                ),
                "next_bar_agreement_probability": _optional_float(
                    subset["next_bar_agreement_label"].mean()
                ),
            }
        )
    return pd.DataFrame(rows)


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, float_format="%.10g")


def build_descriptive_artifacts(
    *,
    one_minute_outcomes: Path,
    five_minute_outcomes: Path,
    outcome_manifest_path: Path,
    config_path: Path,
    surface_output: Path,
    horizon_output: Path,
    weekday_output: Path,
    summary_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    """Build compact aggregate artifacts without optimizing a trading rule."""
    config = _load_yaml(config_path)
    validate_descriptive_config(config)
    outcome_manifest = json.loads(outcome_manifest_path.read_text(encoding="utf-8"))
    if outcome_manifest.get("status") != "development_only":
        raise DescriptiveError("Outcome manifest must remain development-only.")
    one_minute = load_outcomes(
        one_minute_outcomes,
        str(outcome_manifest["one_minute_robustness"]["sha256"]),
    )
    five_minute = load_outcomes(
        five_minute_outcomes,
        str(outcome_manifest["five_minute_primary"]["sha256"]),
    )
    one_events = event_population(one_minute)
    five_events = event_population(five_minute)
    surface_config = config["response_surface"]
    surface, edges = response_surface(
        five_events,
        bin_count=int(surface_config["feature_bins"]),
        low_count_threshold=int(surface_config["low_count_threshold"]),
    )
    uncertainty = config["uncertainty"]
    horizon_config = config["horizon_response"]
    horizon = pd.concat(
        [
            horizon_response(
                five_events,
                resolution_minutes=5,
                horizons=list(horizon_config["five_minute_minutes"]),
                replications=int(uncertainty["replications"]),
                confidence_level=float(uncertainty["confidence_level"]),
                seed=int(uncertainty["seed"]),
            ),
            horizon_response(
                one_events,
                resolution_minutes=1,
                horizons=list(horizon_config["one_minute_minutes"]),
                replications=int(uncertainty["replications"]),
                confidence_level=float(uncertainty["confidence_level"]),
                seed=int(uncertainty["seed"]),
            ),
        ],
        ignore_index=True,
    )
    weekday = weekday_diagnostics(five_events)
    _write_csv(surface, surface_output)
    _write_csv(horizon, horizon_output)
    _write_csv(weekday, weekday_output)

    primary = horizon.loc[
        horizon["resolution_minutes"].eq(5)
        & horizon["direction"].eq("all")
        & horizon["horizon_minutes"].eq(5)
    ].iloc[0]
    one_minute_primary = horizon.loc[
        horizon["resolution_minutes"].eq(1)
        & horizon["direction"].eq("all")
        & horizon["horizon_minutes"].eq(5)
    ].iloc[0]
    summary: dict[str, Any] = {
        "status": "development_only",
        "interpretation": "descriptive_association_not_alpha_or_confirmatory_evidence",
        "population": "feature-ready current body-direction agreement events",
        "feature_bin_edges": edges,
        "primary_five_minute": {
            "event_count": int(primary["event_count"]),
            "session_count": int(primary["session_count"]),
            "mean_signed_nq_return_bps": float(primary["mean_signed_nq_return_bps"]),
            "block_bootstrap_95_ci_bps": [
                float(primary["block_bootstrap_ci_lower_bps"]),
                float(primary["block_bootstrap_ci_upper_bps"]),
            ],
        },
        "one_minute_resolution_five_minute_endpoint": {
            "event_count": int(one_minute_primary["event_count"]),
            "session_count": int(one_minute_primary["session_count"]),
            "mean_signed_nq_return_bps": float(
                one_minute_primary["mean_signed_nq_return_bps"]
            ),
            "block_bootstrap_95_ci_bps": [
                float(one_minute_primary["block_bootstrap_ci_lower_bps"]),
                float(one_minute_primary["block_bootstrap_ci_upper_bps"]),
            ],
        },
        "caveats": [
            "All observations come from development data with no pristine holdout.",
            "Events and forward horizons overlap; session-block intervals preserve clustering.",
            "Feature quantiles describe this development sample and cannot define thresholds.",
            "Persistence means exclude right-censored runs and are descriptive only.",
            "No costs, trade policy, or claim of economic alpha is included.",
        ],
    }
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "descriptive_version": config["descriptive_version"],
        "status": "development_only",
        "generated_at": datetime.now(UTC).isoformat(),
        "inputs": {
            "outcome_manifest_sha256": _hash_file(outcome_manifest_path),
            "config_sha256": _hash_file(config_path),
            "implementation_sha256": _hash_file(Path(__file__)),
            "one_minute_outcomes_sha256": _hash_file(one_minute_outcomes),
            "five_minute_outcomes_sha256": _hash_file(five_minute_outcomes),
        },
        "population_rows": {
            "one_minute": int(len(one_events)),
            "five_minute": int(len(five_events)),
        },
        "artifacts": {
            path.name: {"sha256": _hash_file(path), "committed": True}
            for path in [surface_output, horizon_output, weekday_output, summary_output]
        },
        "limitations": outcome_manifest["limitations"],
    }
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--one-minute-outcomes", type=Path, required=True)
    parser.add_argument("--five-minute-outcomes", type=Path, required=True)
    parser.add_argument("--outcome-manifest", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--surface-output", type=Path, required=True)
    parser.add_argument("--horizon-output", type=Path, required=True)
    parser.add_argument("--weekday-output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    summary = build_descriptive_artifacts(
        one_minute_outcomes=args.one_minute_outcomes,
        five_minute_outcomes=args.five_minute_outcomes,
        outcome_manifest_path=args.outcome_manifest,
        config_path=args.config,
        surface_output=args.surface_output,
        horizon_output=args.horizon_output,
        weekday_output=args.weekday_output,
        summary_output=args.summary_output,
        manifest_output=args.manifest,
    )
    primary = summary["primary_five_minute"]
    print(
        "Built development-only descriptive artifacts: "
        f"primary mean={primary['mean_signed_nq_return_bps']:.3f} bps, "
        f"95% session-block CI={primary['block_bootstrap_95_ci_bps']}."
    )


if __name__ == "__main__":
    main()
