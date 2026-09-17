"""Build feature artifacts for the prespecified CME overnight negative control."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]
import yaml

from btc_nq_coherence.features import (
    PRICE_COLUMNS,
    aggregate_five_minute,
    compute_features,
    load_canonical,
)


class OvernightFeatureError(ValueError):
    """Raised when overnight feature construction differs from the control design."""


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
        raise OvernightFeatureError(f"YAML root must be a mapping: {path}")
    return payload


def validate_overnight_feature_config(config: dict[str, Any]) -> None:
    """Require the primary mathematical definitions in the overnight role."""
    if config.get("schema_version") != 1:
        raise OvernightFeatureError("Overnight feature schema must remain version 1.")
    if config.get("analysis_role") != "overnight_negative_control":
        raise OvernightFeatureError("Feature role must remain overnight negative control.")
    context = config.get("session_context", {})
    expected_context = {
        "calendar": "CME_Equity",
        "session_start_previous_evening": "18:00",
        "session_end": "09:30",
        "signal_bars_only_in_output": True,
        "cross_session_windows": False,
        "pre_session_lookback_minutes": 0,
    }
    if context != expected_context:
        raise OvernightFeatureError("Overnight session context has drifted.")
    resolutions = config.get("resolutions", {})
    if resolutions.get("primary_minutes") != 5 or resolutions.get(
        "robustness_minutes"
    ) != 1:
        raise OvernightFeatureError("Overnight resolutions must remain five and one minute.")
    if resolutions.get("five_minute_alignment") != "UTC":
        raise OvernightFeatureError("Five-minute bars must remain UTC-aligned.")
    if resolutions.get("incomplete_five_minute_bin_policy") != "ineligible":
        raise OvernightFeatureError("Incomplete five-minute bins must be ineligible.")
    body = config.get("candle_body", {})
    if body.get("definition") != "log_close_over_open" or body.get(
        "wicks_or_range_used"
    ) is not False:
        raise OvernightFeatureError("Overnight bodies must match the primary definition.")
    coherence = config.get("coherence", {})
    if coherence.get("per_bar") != "signed_body_direction_product":
        raise OvernightFeatureError("Overnight agreement must match the primary definition.")
    if coherence.get("aggregation") != "unweighted_arithmetic_mean":
        raise OvernightFeatureError("Overnight coherence aggregation has drifted.")
    if coherence.get("scales_minutes") != [15, 30, 60]:
        raise OvernightFeatureError("Overnight coherence scales must remain 15/30/60.")
    scale = config.get("historical_scale", {})
    if scale.get("estimator") != "same_session_slot_mad":
        raise OvernightFeatureError("Overnight scale must use same-slot MAD.")
    if scale.get("lookback_eligible_sessions") != 63:
        raise OvernightFeatureError("Overnight scale must use 63 prior sessions.")
    if scale.get("consistency_constant") != 1.4826:
        raise OvernightFeatureError("MAD consistency constant has drifted.")
    if scale.get("current_session_included") is not False:
        raise OvernightFeatureError("Current overnight session cannot set its own scale.")
    magnitude = config.get("magnitude", {})
    if magnitude.get("joint_intensity") != "geometric_mean":
        raise OvernightFeatureError("Joint intensity has drifted.")
    if magnitude.get("balance") != "normalized_difference":
        raise OvernightFeatureError("Magnitude balance has drifted.")


def build_overnight_context(canonical: pd.DataFrame) -> pd.DataFrame:
    """Select complete registered overnight sessions without additional lookback."""
    required = {
        "overnight_session_date",
        "eligible_overnight_control",
        "nq_contract",
        *PRICE_COLUMNS,
    }
    missing = required.difference(canonical.columns)
    if missing:
        raise OvernightFeatureError(f"Canonical input lacks columns: {sorted(missing)}")
    eligible = canonical["eligible_overnight_control"].astype(bool)
    context = canonical.loc[eligible].copy()
    context["analysis_session_date"] = context["overnight_session_date"].astype(str)
    context["is_signal_bar"] = True
    context["source_valid"] = context[list(PRICE_COLUMNS)].notna().all(axis=1)
    context["source_valid"] &= context["nq_contract"].notna()
    counts = context.groupby("analysis_session_date").size()
    if not counts.eq(930).all():
        raise OvernightFeatureError(
            "Every admitted overnight session must contain 930 minutes."
        )
    if not context["source_valid"].all():
        raise OvernightFeatureError("Eligibility manifest admitted an invalid overnight row.")
    context.index.name = "timestamp_utc"
    return context


def _summary(frame: pd.DataFrame) -> dict[str, Any]:
    ready = frame.loc[frame["feature_ready"]]
    return {
        "rows": int(len(frame)),
        "sessions": int(frame["analysis_session_date"].nunique()),
        "source_valid_rows": int(frame["source_valid"].sum()),
        "feature_ready_rows": int(frame["feature_ready"].sum()),
        "feature_ready_sessions": int(ready["analysis_session_date"].nunique()),
        "state_model_eligible_rows": int(frame["state_model_eligible"].sum()),
        "first_timestamp_utc": frame.index.min().isoformat(),
        "last_timestamp_utc": frame.index.max().isoformat(),
        "first_feature_ready_timestamp_utc": (
            None if ready.empty else ready.index.min().isoformat()
        ),
    }


def build_overnight_feature_artifacts(
    *,
    canonical_path: Path,
    eligibility_manifest_path: Path,
    feature_config_path: Path,
    one_minute_output: Path,
    five_minute_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    """Build one- and five-minute overnight negative-control features."""
    eligibility = json.loads(eligibility_manifest_path.read_text(encoding="utf-8"))
    config = _load_yaml(feature_config_path)
    validate_overnight_feature_config(config)
    if eligibility.get("status") != "development_only":
        raise OvernightFeatureError("Eligibility manifest must remain development-only.")
    expected_hash = str(eligibility["canonical_output"]["sha256"])
    canonical = load_canonical(canonical_path, expected_hash=expected_hash)
    context = build_overnight_context(canonical)
    scales = tuple(int(value) for value in config["coherence"]["scales_minutes"])
    lookback = int(config["historical_scale"]["lookback_eligible_sessions"])
    constant = float(config["historical_scale"]["consistency_constant"])
    one_minute = compute_features(
        context,
        bar_minutes=1,
        coherence_scales_minutes=scales,
        scale_lookback_sessions=lookback,
        mad_constant=constant,
    )
    five_minute = compute_features(
        aggregate_five_minute(context),
        bar_minutes=5,
        coherence_scales_minutes=scales,
        scale_lookback_sessions=lookback,
        mad_constant=constant,
    )
    one_minute_output.parent.mkdir(parents=True, exist_ok=True)
    five_minute_output.parent.mkdir(parents=True, exist_ok=True)
    one_minute.to_csv(
        one_minute_output, index=True, date_format="%Y-%m-%dT%H:%M:%SZ"
    )
    five_minute.to_csv(
        five_minute_output, index=True, date_format="%Y-%m-%dT%H:%M:%SZ"
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "feature_version": config["feature_version"],
        "status": "development_only",
        "role": "overnight_negative_control",
        "generated_at": datetime.now(UTC).isoformat(),
        "inputs": {
            "canonical_sha256": expected_hash,
            "eligibility_manifest_sha256": _hash_file(eligibility_manifest_path),
            "feature_config_sha256": _hash_file(feature_config_path),
            "overnight_implementation_sha256": _hash_file(Path(__file__)),
            "shared_feature_implementation_sha256": _hash_file(
                Path(__file__).with_name("features.py")
            ),
        },
        "definitions": {
            "session": "18:00_previous_evening_to_09:30_America/New_York",
            "expected_minutes_per_session": 930,
            "coherence_scales_minutes": list(scales),
            "same_slot_mad_lookback_sessions": lookback,
            "mad_consistency_constant": constant,
            "primary_bar_minutes": 5,
            "robustness_bar_minutes": 1,
        },
        "one_minute_robustness": {
            **_summary(one_minute),
            "file_name": one_minute_output.name,
            "sha256": _hash_file(one_minute_output),
            "committed": False,
        },
        "five_minute_primary": {
            **_summary(five_minute),
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
    manifest = build_overnight_feature_artifacts(
        canonical_path=args.canonical,
        eligibility_manifest_path=args.eligibility_manifest,
        feature_config_path=args.config,
        one_minute_output=args.one_minute_output,
        five_minute_output=args.five_minute_output,
        manifest_output=args.manifest,
    )
    print(
        "Built overnight negative-control features: "
        f"1m ready={manifest['one_minute_robustness']['feature_ready_rows']:,}; "
        f"5m ready={manifest['five_minute_primary']['feature_ready_rows']:,}."
    )


if __name__ == "__main__":
    main()
