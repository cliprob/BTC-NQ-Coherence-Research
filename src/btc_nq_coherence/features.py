"""Causal candle-body, coherence, intensity, and magnitude-balance features."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any

import pandas as pd  # type: ignore[import-untyped]
import pandas_market_calendars as mcal  # type: ignore[import-untyped]
import yaml


class FeatureError(ValueError):
    """Raised when causal feature construction cannot be completed safely."""


PRICE_COLUMNS = (
    "nq_open",
    "nq_high",
    "nq_low",
    "nq_close",
    "btc_open",
    "btc_high",
    "btc_low",
    "btc_close",
)


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
        raise FeatureError(f"YAML root must be a mapping: {path}")
    return payload


def validate_feature_config(config: dict[str, Any]) -> None:
    """Prevent silent drift from the registered feature definitions."""
    if config.get("schema_version") != 1 or config.get("analysis_role") != "primary":
        raise FeatureError("Feature config must use schema 1 and the primary role.")
    context = config.get("session_context", {})
    if not isinstance(context, dict):
        raise FeatureError("session_context must be a mapping.")
    if context.get("calendar") != "NYSE" or context.get(
        "pre_open_lookback_minutes"
    ) != 60:
        raise FeatureError("Primary context must use NYSE and 60 pre-open minutes.")
    if context.get("cross_session_windows") is not False:
        raise FeatureError("Feature windows cannot cross analysis sessions.")

    resolutions = config.get("resolutions", {})
    if not isinstance(resolutions, dict):
        raise FeatureError("resolutions must be a mapping.")
    if resolutions.get("primary_minutes") != 5 or resolutions.get(
        "robustness_minutes"
    ) != 1:
        raise FeatureError(
            "Feature resolutions must remain 5-minute primary and 1-minute robustness."
        )
    if resolutions.get("five_minute_alignment") != "UTC":
        raise FeatureError("Five-minute bars must remain UTC-aligned.")
    if resolutions.get("incomplete_five_minute_bin_policy") != "ineligible":
        raise FeatureError("Incomplete five-minute bins must be ineligible.")

    body = config.get("candle_body", {})
    if not isinstance(body, dict) or body.get("definition") != "log_close_over_open":
        raise FeatureError("Candle bodies must use log(close/open).")
    if body.get("wicks_or_range_used") is not False:
        raise FeatureError("Primary features cannot use wicks or high-low range.")

    coherence = config.get("coherence", {})
    if not isinstance(coherence, dict):
        raise FeatureError("coherence must be a mapping.")
    if coherence.get("per_bar") != "signed_body_direction_product":
        raise FeatureError("Coherence must use the signed body-direction product.")
    if coherence.get("aggregation") != "unweighted_arithmetic_mean":
        raise FeatureError("Coherence must use an unweighted arithmetic mean.")
    if coherence.get("scales_minutes") != [15, 30, 60]:
        raise FeatureError("Coherence scales must remain 15, 30, and 60 minutes.")

    scale = config.get("historical_scale", {})
    if not isinstance(scale, dict):
        raise FeatureError("historical_scale must be a mapping.")
    if scale.get("estimator") != "same_session_slot_mad":
        raise FeatureError("Historical scale must use same-slot MAD.")
    if scale.get("lookback_eligible_sessions") != 63:
        raise FeatureError("Historical scale must use 63 eligible sessions.")
    if scale.get("consistency_constant") != 1.4826:
        raise FeatureError("MAD consistency constant must remain 1.4826.")
    if scale.get("current_session_included") is not False:
        raise FeatureError("Current session cannot enter its own scale.")

    magnitude = config.get("magnitude", {})
    if not isinstance(magnitude, dict):
        raise FeatureError("magnitude must be a mapping.")
    if magnitude.get("joint_intensity") != "geometric_mean":
        raise FeatureError("Joint intensity must use the geometric mean.")
    if magnitude.get("balance") != "normalized_difference":
        raise FeatureError("Magnitude balance must use the normalized difference.")


def load_canonical(path: Path, expected_hash: str | None = None) -> pd.DataFrame:
    """Load synchronized canonical minutes and verify their registered identity."""
    if not path.is_file():
        raise FeatureError(f"Canonical input does not exist: {path}")
    if expected_hash is not None and _hash_file(path) != expected_hash:
        raise FeatureError("Canonical input hash differs from the eligibility manifest.")
    frame = pd.read_csv(path)
    required = {
        "timestamp_utc",
        "primary_session_date",
        "eligible_primary",
        "nq_contract",
        "nq_volume",
        "btc_volume",
        *PRICE_COLUMNS,
    }
    missing = required.difference(frame.columns)
    if missing:
        raise FeatureError(f"Canonical input is missing columns: {sorted(missing)}")
    frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True)
    frame = frame.set_index("timestamp_utc").sort_index()
    if frame.index.has_duplicates:
        raise FeatureError("Canonical timestamps must be unique.")
    return frame


def build_primary_context(
    canonical: pd.DataFrame, pre_open_minutes: int = 60
) -> pd.DataFrame:
    """Attach valid pre-open context to every eligible XNYS primary session."""
    eligible_rows = canonical.loc[canonical["eligible_primary"].astype(bool)]
    session_dates = sorted(eligible_rows["primary_session_date"].dropna().unique())
    if not session_dates:
        raise FeatureError("Canonical input contains no eligible primary sessions.")
    calendar = mcal.get_calendar("NYSE")
    schedule = calendar.schedule(start_date=session_dates[0], end_date=session_dates[-1])
    sessions: list[pd.DataFrame] = []

    for raw_date in session_dates:
        session_date = str(raw_date)
        label = pd.Timestamp(session_date)
        if label not in schedule.index:
            raise FeatureError(f"Eligible session absent from NYSE calendar: {session_date}")
        market_open = schedule.loc[label, "market_open"]
        market_close = schedule.loc[label, "market_close"]
        expected = pd.date_range(
            start=market_open - pd.Timedelta(minutes=pre_open_minutes),
            end=market_close,
            freq="1min",
            inclusive="left",
        )
        session = canonical.reindex(expected).copy()
        session["analysis_session_date"] = session_date
        session["is_signal_bar"] = session.index >= market_open
        session["source_valid"] = session[list(PRICE_COLUMNS)].notna().all(axis=1)
        session["source_valid"] &= session["nq_contract"].notna()
        cash = session.loc[session["is_signal_bar"]]
        if not cash["source_valid"].all():
            raise FeatureError(
                f"Eligibility manifest admitted incomplete primary session {session_date}."
            )
        sessions.append(session)

    context = pd.concat(sessions).sort_index()
    context.index.name = "timestamp_utc"
    return context


def aggregate_five_minute(context: pd.DataFrame) -> pd.DataFrame:
    """Aggregate complete UTC-aligned five-minute OHLCV bars within each session."""
    aggregated_sessions: list[pd.DataFrame] = []
    for session_date, session in context.groupby("analysis_session_date", sort=True):
        resampler = session.resample("5min", closed="left", label="left", origin="epoch")
        aggregated = resampler.agg(
            {
                "nq_open": "first",
                "nq_high": "max",
                "nq_low": "min",
                "nq_close": "last",
                "nq_volume": "sum",
                "nq_contract": "first",
                "btc_open": "first",
                "btc_high": "max",
                "btc_low": "min",
                "btc_close": "last",
                "btc_volume": "sum",
                "is_signal_bar": "all",
            }
        )
        row_count = resampler.size()
        valid_count = session["source_valid"].astype(int).resample(
            "5min", closed="left", label="left", origin="epoch"
        ).sum()
        contract_count = session["nq_contract"].resample(
            "5min", closed="left", label="left", origin="epoch"
        ).nunique()
        aggregated["source_valid"] = (
            (row_count == 5) & (valid_count == 5) & (contract_count == 1)
        )
        invalid = ~aggregated["source_valid"]
        aggregated.loc[invalid, list(PRICE_COLUMNS)] = math.nan
        aggregated.loc[invalid, ["nq_volume", "btc_volume", "nq_contract"]] = math.nan
        aggregated["analysis_session_date"] = str(session_date)
        aggregated_sessions.append(aggregated)

    result = pd.concat(aggregated_sessions).sort_index()
    result.index.name = "timestamp_utc"
    return result


def _causal_same_slot_mad(values: pd.Series, lookback: int, constant: float) -> pd.Series:
    """Scale each value using only the previous `lookback` finite slot values."""
    result = pd.Series(math.nan, index=values.index, dtype=float)
    history: list[float] = []
    for index, raw_value in values.items():
        if len(history) >= lookback:
            window = history[-lookback:]
            center = float(median(window))
            scale = constant * float(
                median(abs(value - center) for value in window)
            )
            if math.isfinite(scale) and scale > 0:
                result.loc[index] = scale
        value = float(raw_value)
        if math.isfinite(value):
            history.append(value)
    return result


def _add_historical_scales(
    frame: pd.DataFrame, lookback: int, constant: float
) -> pd.DataFrame:
    result = frame.copy()
    local_index = result.index.tz_convert("America/New_York")
    result["session_slot"] = local_index.strftime("%H:%M")
    for asset in ("btc", "nq"):
        output = pd.Series(math.nan, index=result.index, dtype=float)
        for _slot, indexes in result.groupby("session_slot", sort=False).groups.items():
            slot_values = result.loc[indexes, f"{asset}_body"]
            output.loc[indexes] = _causal_same_slot_mad(
                slot_values, lookback=lookback, constant=constant
            )
        result[f"{asset}_body_scale"] = output
    return result


def compute_features(
    bars: pd.DataFrame,
    *,
    bar_minutes: int,
    coherence_scales_minutes: tuple[int, ...] = (15, 30, 60),
    scale_lookback_sessions: int = 63,
    mad_constant: float = 1.4826,
) -> pd.DataFrame:
    """Compute causal features on session-separated bars, then keep signal bars."""
    if any(scale % bar_minutes for scale in coherence_scales_minutes):
        raise FeatureError("Coherence scales must be divisible by the bar interval.")
    result = bars.copy().sort_index()
    for asset in ("btc", "nq"):
        ratio = result[f"{asset}_close"] / result[f"{asset}_open"]
        result[f"{asset}_body"] = ratio.map(
            lambda value: math.log(value)
            if pd.notna(value) and value > 0
            else math.nan
        )
        result[f"{asset}_direction"] = result[f"{asset}_body"].map(
            lambda value: (
                math.nan if pd.isna(value) else int(value > 0) - int(value < 0)
            )
        )
    result["direction_agreement"] = (
        result["btc_direction"] * result["nq_direction"]
    )

    for scale in coherence_scales_minutes:
        bars_in_window = scale // bar_minutes
        result[f"coherence_{scale}m"] = result.groupby(
            "analysis_session_date", sort=False
        )["direction_agreement"].transform(
            lambda values, window=bars_in_window: values.rolling(
                window, min_periods=window
            ).mean()
        )

    result = _add_historical_scales(
        result, lookback=scale_lookback_sessions, constant=mad_constant
    )
    for asset in ("btc", "nq"):
        result[f"{asset}_standardized_body"] = (
            result[f"{asset}_body"] / result[f"{asset}_body_scale"]
        )
        result[f"{asset}_magnitude"] = result[f"{asset}_standardized_body"].abs()

    result["joint_intensity"] = (
        result["btc_magnitude"] * result["nq_magnitude"]
    ).pow(0.5)
    denominator = result["btc_magnitude"] + result["nq_magnitude"]
    result["magnitude_balance"] = (
        (result["btc_magnitude"] - result["nq_magnitude"]) / denominator
    ).where(denominator > 0)
    result["absolute_magnitude_balance"] = result["magnitude_balance"].abs()
    result["common_direction"] = result["nq_direction"].where(
        result["direction_agreement"] == 1
    )

    required_features = [
        *(f"coherence_{scale}m" for scale in coherence_scales_minutes),
        "joint_intensity",
        "magnitude_balance",
        "absolute_magnitude_balance",
    ]
    result["feature_ready"] = result["source_valid"].astype(bool)
    result["feature_ready"] &= result[required_features].notna().all(axis=1)
    result["state_model_eligible"] = result["feature_ready"] & (
        result["direction_agreement"] == 1
    )
    result["bar_minutes"] = bar_minutes
    result["feature_available_timestamp_utc"] = result.index + pd.Timedelta(
        minutes=bar_minutes
    )
    return result.loc[result["is_signal_bar"].astype(bool)].copy()


def _feature_summary(frame: pd.DataFrame) -> dict[str, Any]:
    ready = frame.loc[frame["feature_ready"]]
    return {
        "rows": int(len(frame)),
        "source_valid_rows": int(frame["source_valid"].sum()),
        "feature_ready_rows": int(frame["feature_ready"].sum()),
        "state_model_eligible_rows": int(frame["state_model_eligible"].sum()),
        "first_timestamp_utc": frame.index.min().isoformat(),
        "last_timestamp_utc": frame.index.max().isoformat(),
        "first_feature_ready_timestamp_utc": (
            None if ready.empty else ready.index.min().isoformat()
        ),
    }


def build_feature_artifacts(
    *,
    canonical_path: Path,
    eligibility_manifest_path: Path,
    feature_config_path: Path,
    one_minute_output: Path,
    five_minute_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    """Build 1-minute robustness and 5-minute primary feature artifacts."""
    eligibility = json.loads(eligibility_manifest_path.read_text(encoding="utf-8"))
    feature_config = _load_yaml(feature_config_path)
    validate_feature_config(feature_config)
    if eligibility.get("status") != "development_only":
        raise FeatureError("Current eligibility manifest must remain development-only.")
    expected_hash = str(eligibility["canonical_output"]["sha256"])
    canonical = load_canonical(canonical_path, expected_hash=expected_hash)
    context_config = feature_config["session_context"]
    scale_config = feature_config["historical_scale"]
    coherence_config = feature_config["coherence"]
    context = build_primary_context(
        canonical, pre_open_minutes=int(context_config["pre_open_lookback_minutes"])
    )
    scales = tuple(int(value) for value in coherence_config["scales_minutes"])
    lookback = int(scale_config["lookback_eligible_sessions"])
    constant = float(scale_config["consistency_constant"])

    one_minute = compute_features(
        context,
        bar_minutes=1,
        coherence_scales_minutes=scales,
        scale_lookback_sessions=lookback,
        mad_constant=constant,
    )
    five_minute_bars = aggregate_five_minute(context)
    five_minute = compute_features(
        five_minute_bars,
        bar_minutes=5,
        coherence_scales_minutes=scales,
        scale_lookback_sessions=lookback,
        mad_constant=constant,
    )

    one_minute_output.parent.mkdir(parents=True, exist_ok=True)
    five_minute_output.parent.mkdir(parents=True, exist_ok=True)
    one_minute.to_csv(one_minute_output, index=True, date_format="%Y-%m-%dT%H:%M:%SZ")
    five_minute.to_csv(five_minute_output, index=True, date_format="%Y-%m-%dT%H:%M:%SZ")

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "feature_version": feature_config["feature_version"],
        "status": "development_only",
        "generated_at": datetime.now(UTC).isoformat(),
        "inputs": {
            "canonical_sha256": expected_hash,
            "eligibility_manifest_sha256": _hash_file(eligibility_manifest_path),
            "feature_config_sha256": _hash_file(feature_config_path),
            "feature_implementation_sha256": _hash_file(Path(__file__)),
        },
        "definitions": {
            "bar_timestamp_semantics": "bar_open",
            "feature_available_timestamp_semantics": "bar_close",
            "coherence_scales_minutes": list(scales),
            "same_slot_mad_lookback_sessions": lookback,
            "mad_consistency_constant": constant,
            "primary_bar_minutes": 5,
            "robustness_bar_minutes": 1,
        },
        "one_minute_robustness": {
            **_feature_summary(one_minute),
            "file_name": one_minute_output.name,
            "sha256": _hash_file(one_minute_output),
            "committed": False,
        },
        "five_minute_primary": {
            **_feature_summary(five_minute),
            "file_name": five_minute_output.name,
            "sha256": _hash_file(five_minute_output),
            "committed": False,
        },
        "limitations": eligibility["limitations"],
    }
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--eligibility-manifest", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--one-minute-output", type=Path, required=True)
    parser.add_argument("--five-minute-output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_feature_artifacts(
        canonical_path=args.canonical,
        eligibility_manifest_path=args.eligibility_manifest,
        feature_config_path=args.config,
        one_minute_output=args.one_minute_output,
        five_minute_output=args.five_minute_output,
        manifest_output=args.manifest,
    )
    print(
        "Built causal features: "
        f"1m ready={manifest['one_minute_robustness']['feature_ready_rows']:,}; "
        f"5m ready={manifest['five_minute_primary']['feature_ready_rows']:,}."
    )


if __name__ == "__main__":
    main()
