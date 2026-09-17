"""Causal state-persistence and open-to-open NQ outcome construction."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]
import yaml


class OutcomeError(ValueError):
    """Raised when outcome construction would violate registered timing rules."""


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
        raise OutcomeError(f"YAML root must be a mapping: {path}")
    return payload


def validate_outcome_config(config: dict[str, Any]) -> None:
    """Prevent silent drift in label timing or registered horizons."""
    if config.get("schema_version") != 1 or config.get("status") != "development_only":
        raise OutcomeError("Outcome config must remain schema 1 and development-only.")
    timing = config.get("timing", {})
    if not isinstance(timing, dict):
        raise OutcomeError("timing must be a mapping.")
    expected_timing = {
        "feature_timestamp": "bar_open",
        "feature_available": "bar_close",
        "entry_price": "next_bar_open",
        "exit_price": "horizon_open",
        "return_type": "log",
        "cross_session_labels": False,
    }
    if any(timing.get(key) != value for key, value in expected_timing.items()):
        raise OutcomeError("Outcome timing differs from the registered causal specification.")
    state = config.get("state", {})
    if not isinstance(state, dict) or state.get("session_end_policy") != "right_censored":
        raise OutcomeError("Persistence duration must be right-censored at session end.")
    economic = config.get("economic", {})
    if not isinstance(economic, dict):
        raise OutcomeError("economic must be a mapping.")
    if economic.get("primary_horizon_minutes") != 5:
        raise OutcomeError("Primary economic horizon must remain five minutes.")
    if economic.get("secondary_horizons_minutes") != [15, 30, 60]:
        raise OutcomeError("Secondary economic horizons must remain 15/30/60 minutes.")
    if economic.get("one_minute_timing_path_minutes") != [1, 2, 3, 4, 5]:
        raise OutcomeError("One-minute timing path must remain +1 through +5 minutes.")


def load_features(path: Path, expected_hash: str) -> pd.DataFrame:
    """Load a registered feature artifact with UTC timestamp columns."""
    if not path.is_file() or _hash_file(path) != expected_hash:
        raise OutcomeError(f"Feature artifact identity mismatch: {path}")
    frame = pd.read_csv(path)
    required = {
        "timestamp_utc",
        "feature_available_timestamp_utc",
        "analysis_session_date",
        "bar_minutes",
        "nq_open",
        "direction_agreement",
        "common_direction",
        "feature_ready",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise OutcomeError(f"Feature artifact is missing columns: {sorted(missing)}")
    frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True)
    frame["feature_available_timestamp_utc"] = pd.to_datetime(
        frame["feature_available_timestamp_utc"], utc=True
    )
    frame = frame.set_index("timestamp_utc").sort_index()
    if frame.index.has_duplicates:
        raise OutcomeError("Feature timestamps must be unique.")
    return frame


def _add_state_outcomes(frame: pd.DataFrame, bar_minutes: int) -> pd.DataFrame:
    result = frame.copy()
    next_timestamp = result.index + pd.Timedelta(minutes=bar_minutes)
    next_direction = result["direction_agreement"].reindex(next_timestamp).to_numpy()
    next_session = result["analysis_session_date"].reindex(next_timestamp).to_numpy()
    same_session = next_session == result["analysis_session_date"].to_numpy()
    result["next_bar_direction_agreement"] = pd.Series(
        next_direction, index=result.index
    ).where(same_session)
    current_agreement = result["direction_agreement"] == 1
    result["next_bar_agreement_label"] = (
        result["next_bar_direction_agreement"] == 1
    ).astype(float)
    result.loc[
        ~current_agreement | result["next_bar_direction_agreement"].isna(),
        "next_bar_agreement_label",
    ] = math.nan

    run_bars = pd.Series(math.nan, index=result.index, dtype=float)
    event_observed = pd.Series(pd.NA, index=result.index, dtype="boolean")
    for _session_date, indexes in result.groupby(
        "analysis_session_date", sort=True
    ).groups.items():
        directions = result.loc[indexes, "direction_agreement"].to_numpy()
        ordered_indexes = list(indexes)
        for position, index in enumerate(ordered_indexes):
            if directions[position] != 1:
                continue
            future_position = position + 1
            duration = 0
            while (
                future_position < len(directions)
                and ordered_indexes[future_position]
                == ordered_indexes[future_position - 1]
                + pd.Timedelta(minutes=bar_minutes)
                and directions[future_position] == 1
            ):
                duration += 1
                future_position += 1
            run_bars.loc[index] = duration
            event_observed.loc[index] = (
                future_position < len(directions)
                and ordered_indexes[future_position]
                == ordered_indexes[future_position - 1]
                + pd.Timedelta(minutes=bar_minutes)
            )

    result["persistence_run_bars"] = run_bars
    result["persistence_run_minutes"] = run_bars * bar_minutes
    result["persistence_end_observed"] = event_observed
    result["persistence_right_censored"] = event_observed.map(
        lambda value: pd.NA if pd.isna(value) else not bool(value)
    ).astype("boolean")
    return result


def _add_return_outcome(
    frame: pd.DataFrame, *, bar_minutes: int, horizon_minutes: int
) -> None:
    entry_timestamp = frame.index + pd.Timedelta(minutes=bar_minutes)
    exit_timestamp = entry_timestamp + pd.Timedelta(minutes=horizon_minutes)
    opens = frame["nq_open"]
    sessions = frame["analysis_session_date"]
    entry_open = opens.reindex(entry_timestamp).to_numpy()
    exit_open = opens.reindex(exit_timestamp).to_numpy()
    entry_session = sessions.reindex(entry_timestamp).to_numpy()
    exit_session = sessions.reindex(exit_timestamp).to_numpy()
    current_session = sessions.to_numpy()
    valid = (
        (entry_session == current_session)
        & (exit_session == current_session)
        & pd.notna(entry_open)
        & pd.notna(exit_open)
        & (entry_open > 0)
        & (exit_open > 0)
    )
    raw_return = pd.Series(math.nan, index=frame.index, dtype=float)
    raw_return.loc[valid] = [
        math.log(exit_value / entry_value)
        for entry_value, exit_value in zip(
            entry_open[valid], exit_open[valid], strict=True
        )
    ]
    signed_return = raw_return * frame["common_direction"]
    suffix = f"{horizon_minutes}m"
    frame[f"nq_log_return_{suffix}"] = raw_return
    frame[f"nq_return_bps_{suffix}"] = raw_return * 10_000.0
    frame[f"signed_nq_log_return_{suffix}"] = signed_return
    frame[f"signed_nq_return_bps_{suffix}"] = signed_return * 10_000.0
    frame[f"outcome_ready_{suffix}"] = raw_return.notna()


def build_outcomes(
    frame: pd.DataFrame, *, bar_minutes: int, horizons_minutes: tuple[int, ...]
) -> pd.DataFrame:
    """Create causal state and economic outcomes without crossing sessions."""
    if any(horizon <= 0 or horizon % bar_minutes for horizon in horizons_minutes):
        raise OutcomeError("Every horizon must be a positive multiple of bar_minutes.")
    if not frame["bar_minutes"].eq(bar_minutes).all():
        raise OutcomeError("Input bar_minutes differs from the requested resolution.")
    expected_availability = frame.index + pd.Timedelta(minutes=bar_minutes)
    actual_availability = pd.to_datetime(
        frame["feature_available_timestamp_utc"], utc=True
    )
    if not actual_availability.eq(expected_availability).all():
        raise OutcomeError("Feature availability must equal the event-bar close.")
    result = _add_state_outcomes(frame, bar_minutes=bar_minutes)
    for horizon in horizons_minutes:
        _add_return_outcome(
            result, bar_minutes=bar_minutes, horizon_minutes=horizon
        )
    result["outcome_entry_timestamp_utc"] = expected_availability
    result["primary_outcome_exit_timestamp_utc"] = (
        result["outcome_entry_timestamp_utc"] + pd.Timedelta(minutes=5)
    )
    return result


def _summary(frame: pd.DataFrame, horizons: tuple[int, ...]) -> dict[str, Any]:
    current_agreement = frame["direction_agreement"] == 1
    payload: dict[str, Any] = {
        "rows": int(len(frame)),
        "current_agreement_rows": int(current_agreement.sum()),
        "next_bar_labels": int(frame["next_bar_agreement_label"].notna().sum()),
        "uncensored_persistence_rows": int(
            frame["persistence_end_observed"].fillna(False).sum()
        ),
        "right_censored_persistence_rows": int(
            frame["persistence_right_censored"].fillna(False).sum()
        ),
        "valid_return_rows": {
            f"{horizon}m": int(frame[f"outcome_ready_{horizon}m"].sum())
            for horizon in horizons
        },
    }
    return payload


def build_outcome_artifacts(
    *,
    one_minute_features: Path,
    five_minute_features: Path,
    feature_manifest_path: Path,
    outcome_config_path: Path,
    one_minute_output: Path,
    five_minute_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    """Build registered outcome files for both protocol resolutions."""
    feature_manifest = json.loads(feature_manifest_path.read_text(encoding="utf-8"))
    config = _load_yaml(outcome_config_path)
    validate_outcome_config(config)
    if feature_manifest.get("status") != "development_only":
        raise OutcomeError("Feature manifest must remain development-only.")

    one_minute = load_features(
        one_minute_features,
        expected_hash=str(feature_manifest["one_minute_robustness"]["sha256"]),
    )
    five_minute = load_features(
        five_minute_features,
        expected_hash=str(feature_manifest["five_minute_primary"]["sha256"]),
    )
    one_horizons = (1, 2, 3, 4, 5, 15, 30, 60)
    five_horizons = (5, 15, 30, 60)
    one_outcomes = build_outcomes(
        one_minute, bar_minutes=1, horizons_minutes=one_horizons
    )
    five_outcomes = build_outcomes(
        five_minute, bar_minutes=5, horizons_minutes=five_horizons
    )

    one_minute_output.parent.mkdir(parents=True, exist_ok=True)
    five_minute_output.parent.mkdir(parents=True, exist_ok=True)
    one_outcomes.to_csv(
        one_minute_output, index=True, date_format="%Y-%m-%dT%H:%M:%SZ"
    )
    five_outcomes.to_csv(
        five_minute_output, index=True, date_format="%Y-%m-%dT%H:%M:%SZ"
    )

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "outcome_version": config["outcome_version"],
        "status": "development_only",
        "generated_at": datetime.now(UTC).isoformat(),
        "inputs": {
            "feature_manifest_sha256": _hash_file(feature_manifest_path),
            "outcome_config_sha256": _hash_file(outcome_config_path),
            "outcome_implementation_sha256": _hash_file(Path(__file__)),
        },
        "definitions": {
            "primary_horizon_minutes": 5,
            "secondary_horizons_minutes": [15, 30, 60],
            "one_minute_timing_path_minutes": [1, 2, 3, 4, 5],
            "entry": "next_bar_open",
            "exit": "horizon_open",
            "session_end": "right_censor_state_and_invalidate_cross_session_return",
        },
        "one_minute_robustness": {
            **_summary(one_outcomes, one_horizons),
            "file_name": one_minute_output.name,
            "sha256": _hash_file(one_minute_output),
            "committed": False,
        },
        "five_minute_primary": {
            **_summary(five_outcomes, five_horizons),
            "file_name": five_minute_output.name,
            "sha256": _hash_file(five_minute_output),
            "committed": False,
        },
        "limitations": feature_manifest["limitations"],
    }
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--one-minute-features", type=Path, required=True)
    parser.add_argument("--five-minute-features", type=Path, required=True)
    parser.add_argument("--feature-manifest", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--one-minute-output", type=Path, required=True)
    parser.add_argument("--five-minute-output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_outcome_artifacts(
        one_minute_features=args.one_minute_features,
        five_minute_features=args.five_minute_features,
        feature_manifest_path=args.feature_manifest,
        outcome_config_path=args.config,
        one_minute_output=args.one_minute_output,
        five_minute_output=args.five_minute_output,
        manifest_output=args.manifest,
    )
    print(
        "Built causal outcomes: "
        f"1m 5-minute labels="
        f"{manifest['one_minute_robustness']['valid_return_rows']['5m']:,}; "
        f"5m labels={manifest['five_minute_primary']['valid_return_rows']['5m']:,}."
    )


if __name__ == "__main__":
    main()
