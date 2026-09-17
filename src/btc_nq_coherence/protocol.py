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
    if protocol["design"].get("primary_horizon_minutes") != 5:
        raise ProtocolError("The primary economic return horizon must be five minutes.")
    if horizons != [5, 15, 30, 60]:
        raise ProtocolError(
            "Return horizons must be the 5-minute primary and 15/30/60-minute secondary curve."
        )

    economic_return = protocol["design"].get("economic_return", {})
    if economic_return.get("price_basis") != "next_open_to_horizon_open":
        raise ProtocolError("Economic returns must use next-open to horizon-open prices.")
    if economic_return.get("primary_horizon_minutes") != 5:
        raise ProtocolError("Economic-return configuration must preserve the 5-minute primary.")
    if economic_return.get("primary_five_minute_bars") != 1:
        raise ProtocolError("The 5-minute primary must span one future 5-minute bar.")
    if economic_return.get("robustness_one_minute_bars") != 5:
        raise ProtocolError("The 1-minute robustness primary must span five future bars.")
    if economic_return.get("one_minute_timing_diagnostics_minutes") != [1, 2, 3, 4, 5]:
        raise ProtocolError("One-minute timing diagnostics must report +1 through +5 minutes.")
    if economic_return.get("secondary_response_horizons_minutes") != [15, 30, 60]:
        raise ProtocolError("Secondary economic horizons must be 15, 30, and 60 minutes.")
    if economic_return.get("intermediate_diagnostics_secondary_only") is not True:
        raise ProtocolError("Intermediate one-minute responses must remain secondary.")
    if economic_return.get("secondary_may_replace_primary") is not False:
        raise ProtocolError("A secondary horizon cannot replace the five-minute primary.")
    if economic_return.get("target_must_remain_in_primary_session") is not True:
        raise ProtocolError("Economic-return targets must remain in the primary session.")

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

    sessions = design.get("session_scope", {})
    if sessions.get("timezone") != "America/New_York":
        raise ProtocolError("Session scope must be DST-aware America/New_York.")
    if sessions.get("interval_semantics") != "left_closed_right_open":
        raise ProtocolError("Session bars must use left-closed, right-open intervals.")
    primary_session = sessions.get("primary", {})
    if primary_session.get("calendar") != "XNYS":
        raise ProtocolError("Primary session must use the XNYS calendar.")
    if primary_session.get("nominal_open") != "09:30":
        raise ProtocolError("Primary session must open at 09:30 New York time.")
    if primary_session.get("nominal_close") != "16:00":
        raise ProtocolError("Primary session must close at 16:00 New York time.")
    if primary_session.get("early_close_policy") != "official_calendar_close":
        raise ProtocolError("Primary session must honor official early closes.")
    if primary_session.get("signal_after_bar_close") is not True:
        raise ProtocolError("Primary signals must form after bar close.")
    if primary_session.get("target_must_end_by_official_close") is not True:
        raise ProtocolError("Primary targets must end by the official close.")
    if primary_session.get("exit_must_end_by_official_close") is not True:
        raise ProtocolError("Primary exits must occur by the official close.")
    if primary_session.get("truncate_target_or_position_at_close") is not False:
        raise ProtocolError("Targets and positions cannot be truncated at the close.")
    if primary_session.get("carry_position_overnight") is not False:
        raise ProtocolError("Primary positions cannot be carried overnight.")
    if primary_session.get("causal_lookback_may_precede_open") is not True:
        raise ProtocolError("Causal lookbacks must preserve information at the open.")
    if primary_session.get("pre_open_bars_may_be_signals_or_outcomes") is not False:
        raise ProtocolError("Pre-open bars cannot be primary signals or outcomes.")

    overnight = sessions.get("overnight_negative_control", {})
    if overnight.get("enabled") is not True:
        raise ProtocolError("The overnight negative control must be enabled.")
    if overnight.get("required_regardless_of_primary_result") is not True:
        raise ProtocolError("The overnight negative control is mandatory.")
    if overnight.get("calendar") != "CME_equity_futures":
        raise ProtocolError("Overnight control must use the CME equity calendar.")
    if overnight.get("start_previous_evening") != "18:00":
        raise ProtocolError("Overnight control must start at 18:00 New York time.")
    if overnight.get("end") != "09:30":
        raise ProtocolError("Overnight control must end at 09:30 New York time.")
    if overnight.get("excludes_maintenance_break") is not True:
        raise ProtocolError("Overnight control must exclude CME maintenance.")
    if overnight.get("excludes_weekends_and_holidays") is not True:
        raise ProtocolError("Overnight control must exclude weekends and holidays.")
    if overnight.get("separately_reported") is not True:
        raise ProtocolError("Overnight control must be reported separately.")
    if overnight.get("may_select_or_replace_primary_parameters") is not False:
        raise ProtocolError("Overnight results cannot select primary parameters.")
    if overnight.get("post_cash_pre_maintenance_included") is not False:
        raise ProtocolError("Post-cash trading is outside the overnight control.")

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
    scale = magnitude.get("historical_scale", {})
    if scale.get("estimator") != "same_session_slot_mad":
        raise ProtocolError("Historical body scale must use same-slot MAD.")
    if scale.get("mad_consistency_constant") != 1.4826:
        raise ProtocolError("MAD consistency constant must be 1.4826.")
    if scale.get("lookback_eligible_sessions") != 63:
        raise ProtocolError("Historical body scale must use 63 eligible sessions.")
    if scale.get("reference_sessions") != "analysis_calendar_eligible_sessions":
        raise ProtocolError("BTC and NQ must use the same eligible analysis sessions.")
    if scale.get("slot_timezone") != "America/New_York":
        raise ProtocolError("Historical scale slots must be DST-aware New York time.")
    if scale.get("separate_by_asset") is not True:
        raise ProtocolError("Historical scale must be separate for each asset.")
    if scale.get("separate_by_resolution") is not True:
        raise ProtocolError("Historical scale must be separate for each resolution.")
    if scale.get("include_current_session") is not False:
        raise ProtocolError("The current session cannot enter its own historical scale.")
    if scale.get("current_body_centering") != "none":
        raise ProtocolError("The current body must not be median-centered.")
    if scale.get("missing_slot_policy") != "extend_back_until_63_valid":
        raise ProtocolError("Missing slots must extend the causal lookback.")
    if scale.get("minimum_valid_observations") != 63:
        raise ProtocolError("Historical scale requires 63 valid observations.")
    if scale.get("zero_or_nonfinite_scale_policy") != "ineligible":
        raise ProtocolError("Zero or non-finite historical scale must be ineligible.")
    if scale.get("epsilon_floor") is not None:
        raise ProtocolError("Historical scale cannot use an epsilon floor.")
    if scale.get("cross_slot_fallback") is not False:
        raise ProtocolError("Historical scale cannot use cross-slot fallback.")
    if scale.get("future_data_fallback") is not False:
        raise ProtocolError("Historical scale cannot use future-data fallback.")
    if scale.get("roll_or_known_gap_policy") != "ineligible":
        raise ProtocolError("Roll- or gap-contaminated scale inputs must be ineligible.")
    if scale.get("online_update_from_completed_prior_sessions") is not True:
        raise ProtocolError("Historical scale must update causally between sessions.")
    if protocol["data"].get("minimum_pre_sample_warmup_sessions") != 63:
        raise ProtocolError("The dataset must provide a 63-session warm-up.")
    current_iteration = protocol["data"].get("current_iteration", {})
    if current_iteration.get("mode") != "development_only":
        raise ProtocolError("The current available-data iteration must be development-only.")
    if current_iteration.get("complete_primary_sessions_before_warmup") != 458:
        raise ProtocolError("Current primary-session eligibility must match the data manifest.")
    if current_iteration.get("complete_overnight_sessions_before_warmup") != 551:
        raise ProtocolError("Current overnight eligibility must match the data manifest.")
    if current_iteration.get("exclude_incomplete_session_entirely") is not True:
        raise ProtocolError("Incomplete sessions must be excluded in full.")
    if current_iteration.get("exclude_contract_transition_session") is not True:
        raise ProtocolError("Contract-transition sessions must be excluded in full.")
    if current_iteration.get("forward_fill_prices") is not False:
        raise ProtocolError("The current study cannot forward-fill prices.")
    if current_iteration.get("pre_etp_sample_available") is not False:
        raise ProtocolError("The current files do not contain a pre-ETP sample.")
    if current_iteration.get("pristine_final_holdout_available") is not False:
        raise ProtocolError("The current files do not contain a pristine final holdout.")
    if current_iteration.get("confirmatory_claims_permitted") is not False:
        raise ProtocolError("Confirmatory claims are prohibited for the current files.")
    if current_iteration.get("weekday_sampling_imbalance_present") is not True:
        raise ProtocolError("The observed weekday sampling imbalance must be disclosed.")
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
            .get("historical_scale", {})
            .get("estimator"),
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
