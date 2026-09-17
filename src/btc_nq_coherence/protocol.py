"""Validation for the machine-readable research protocol."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


class ProtocolError(ValueError):
    """Raised when the research protocol violates its schema invariants."""


def load_protocol(path: Path) -> dict[str, Any]:
    """Load and validate a protocol YAML file."""
    with path.open(encoding="utf-8") as stream:
        payload = yaml.safe_load(stream)
    if not isinstance(payload, dict):
        raise ProtocolError("Protocol root must be a mapping.")
    validate_protocol(payload)
    return payload


def validate_protocol(protocol: dict[str, Any]) -> None:
    """Validate invariants needed before any research stage can run."""
    required_sections = {"research", "design", "data", "governance"}
    missing = required_sections.difference(protocol)
    if missing:
        raise ProtocolError(f"Missing protocol sections: {sorted(missing)}")

    if protocol.get("schema_version") != 1:
        raise ProtocolError("Unsupported schema_version; expected 1.")

    status = protocol.get("status")
    if status not in {"draft", "frozen"}:
        raise ProtocolError("status must be 'draft' or 'frozen'.")

    question = protocol["research"].get("primary_question", "")
    if not isinstance(question, str) or not question.strip():
        raise ProtocolError("A non-empty primary_question is required.")

    hypotheses = protocol["research"].get("hypotheses", [])
    if not hypotheses:
        raise ProtocolError("At least one hypothesis is required.")
    hypothesis_ids = [item.get("id") for item in hypotheses]
    if len(hypothesis_ids) != len(set(hypothesis_ids)):
        raise ProtocolError("Hypothesis IDs must be unique.")

    horizons = protocol["design"].get("candidate_horizons_minutes", [])
    if not horizons or any(not isinstance(value, int) or value <= 0 for value in horizons):
        raise ProtocolError("Candidate horizons must be positive integer minutes.")
    if horizons != sorted(set(horizons)):
        raise ProtocolError("Candidate horizons must be sorted and unique.")

    if protocol["design"].get("coherence_excludes_magnitude") is not True:
        raise ProtocolError(
            "Coherence must exclude joint intensity and magnitude balance."
        )
    if protocol["design"].get("primary_candle_component") != (
        "log_close_over_open_body"
    ):
        raise ProtocolError("The primary candle component must be the signed body return.")
    if protocol["design"].get("primary_uses_wicks_or_range") is not False:
        raise ProtocolError(
            "Wicks and high-low range must be excluded from the primary design."
        )

    coherence = protocol["design"].get("coherence_measure", {})
    if coherence.get("per_bar_agreement") != "signed_body_direction_product":
        raise ProtocolError("Coherence must use the signed body-direction product.")
    if coherence.get("aggregation") != "unweighted_arithmetic_mean":
        raise ProtocolError("Coherence must use the unweighted arithmetic mean.")
    if coherence.get("scales_minutes") != [15, 30, 60]:
        raise ProtocolError("Coherence scales must be exactly 15, 30, and 60 minutes.")
    if coherence.get("use_scales_jointly") is not True:
        raise ProtocolError("All coherence scales must be used jointly.")

    state_models = protocol["design"].get("state_model_comparison", {})
    if state_models.get("pnl_selection_prohibited") is not True:
        raise ProtocolError("Trading P&L cannot select the coherence state model.")
    if state_models.get("coherence_threshold") is not None:
        raise ProtocolError("A coherence threshold cannot be set before strategy research.")
    if state_models.get("threshold_stage") != "strategy_only":
        raise ProtocolError("Coherence thresholds belong only to the strategy stage.")

    design = protocol["design"]
    if design.get("primary_bar_minutes") != 5:
        raise ProtocolError("The primary bar interval must be five minutes.")
    if design.get("robustness_bar_minutes") != [1]:
        raise ProtocolError("The robustness bar interval must be one minute.")
    if design.get("run_robustness_regardless_of_primary_result") is not True:
        raise ProtocolError("The one-minute robustness analysis is mandatory.")

    construction = design.get("bar_construction", {})
    if construction.get("source_bar_minutes") != 1:
        raise ProtocolError("Five-minute bars must derive from one-minute source data.")
    if construction.get("primary_derived_from_source") is not True:
        raise ProtocolError("Primary bars must be derived from the registered source data.")
    if construction.get("alignment_timezone") != "UTC":
        raise ProtocolError("Derived bars must use UTC-aligned boundaries.")
    expected_ohlcv = {
        "open": "first",
        "high": "maximum",
        "low": "minimum",
        "close": "last",
        "volume": "sum",
    }
    if any(construction.get(field) != rule for field, rule in expected_ohlcv.items()):
        raise ProtocolError("Derived bars must use the registered OHLCV aggregation rules.")
    if construction.get("incomplete_bin_policy") != "ineligible":
        raise ProtocolError("Incomplete aggregated bars must be ineligible.")
    if construction.get("forward_fill_prices") is not False:
        raise ProtocolError("Market prices must not be forward-filled.")
    if construction.get("may_cross_session_roll_or_known_gap") is not False:
        raise ProtocolError("Bars cannot cross sessions, rolls, or known gaps.")
    if construction.get("coherence_scales_are_clock_time") is not True:
        raise ProtocolError("Coherence scales must remain fixed in clock time.")

    magnitude = design.get("magnitude_coordinates", {})
    if magnitude.get("normalized_body_magnitude") != "absolute_standardized_body":
        raise ProtocolError("Magnitude must use the absolute standardized body.")
    if magnitude.get("historical_scale_must_be_causal") is not True:
        raise ProtocolError("The historical body scale must be causal.")
    if magnitude.get("joint_intensity") != "geometric_mean":
        raise ProtocolError("Joint intensity must use the geometric mean.")
    if magnitude.get("magnitude_balance") != "normalized_difference":
        raise ProtocolError("Magnitude balance must use the normalized difference.")
    if magnitude.get("magnitude_balance_range") != [-1, 1]:
        raise ProtocolError("Magnitude balance must be bounded on [-1, 1].")
    if magnitude.get("zero_denominator_policy") != "ineligible":
        raise ProtocolError("Zero-denominator magnitude balance must be ineligible.")
    if magnitude.get("coefficient_sign_constraints") != "none":
        raise ProtocolError("Magnitude coefficient signs must not be constrained.")

    expected_m0 = [
        "coherence_15m",
        "coherence_30m",
        "coherence_60m",
        "common_direction",
    ]
    expected_m1_additions = [
        "joint_intensity",
        "magnitude_balance",
        "absolute_magnitude_balance",
    ]
    if state_models.get("m0_predictors") != expected_m0:
        raise ProtocolError("M0 must include coherence scales and common direction.")
    if state_models.get("m1_additional_predictors") != expected_m1_additions:
        raise ProtocolError("M1 must add joint intensity, balance, and absolute balance.")

    frozen = bool(protocol["governance"].get("protocol_frozen"))
    if status == "frozen" and not frozen:
        raise ProtocolError("A frozen protocol must set governance.protocol_frozen=true.")
    if status == "frozen":
        unresolved = {
            "primary_horizon_minutes": protocol["design"].get("primary_horizon_minutes"),
            "historical_scale_estimator": protocol["design"]
            .get("magnitude_coordinates", {})
            .get("historical_scale_estimator"),
            "final_holdout_start": protocol["data"].get("final_holdout_start"),
            "final_holdout_end": protocol["data"].get("final_holdout_end"),
        }
        missing_values = [name for name, value in unresolved.items() if value is None]
        if missing_values:
            raise ProtocolError(
                f"Frozen protocol has unresolved values: {sorted(missing_values)}"
            )


def main() -> None:
    """Validate a protocol from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to research protocol YAML")
    args = parser.parse_args()
    protocol = load_protocol(args.path)
    print(
        f"Valid {protocol['status']} protocol "
        f"v{protocol['protocol_version']} ({args.path})"
    )


if __name__ == "__main__":
    main()
