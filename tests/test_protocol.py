from pathlib import Path

import pytest

from btc_nq_coherence.protocol import ProtocolError, load_protocol, validate_protocol

ROOT = Path(__file__).resolve().parents[1]


def test_repository_protocol_is_closed_development_record() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")

    assert protocol["status"] == "completed_development"
    assert protocol["protocol_version"] == "1.0.0"
    assert protocol["governance"]["protocol_frozen"] is True
    assert protocol["governance"]["freeze_scope"] == "completed_development_record"
    assert protocol["governance"]["preregistered"] is False
    assert protocol["governance"]["frozen_after_results"] is True
    assert protocol["design"]["strategy_stage_locked"] is True
    assert protocol["design"]["coherence_excludes_magnitude"] is True
    assert protocol["design"]["primary_candle_component"] == (
        "log_close_over_open_body"
    )
    assert protocol["design"]["primary_uses_wicks_or_range"] is False
    assert protocol["design"]["coherence_measure"]["scales_minutes"] == [15, 30, 60]
    assert protocol["design"]["coherence_measure"]["use_scales_jointly"] is True
    assert protocol["design"]["primary_bar_minutes"] == 5
    assert protocol["design"]["robustness_bar_minutes"] == [1]
    assert protocol["design"]["run_robustness_regardless_of_primary_result"] is True
    assert protocol["design"]["primary_horizon_minutes"] == 5
    assert protocol["design"]["candidate_horizons_minutes"] == [5, 15, 30, 60]
    economic_return = protocol["design"]["economic_return"]
    assert economic_return["price_basis"] == "next_open_to_horizon_open"
    assert economic_return["primary_five_minute_bars"] == 1
    assert economic_return["robustness_one_minute_bars"] == 5
    assert economic_return["one_minute_timing_diagnostics_minutes"] == [1, 2, 3, 4, 5]
    assert economic_return["secondary_response_horizons_minutes"] == [15, 30, 60]
    assert economic_return["secondary_may_replace_primary"] is False
    sessions = protocol["design"]["session_scope"]
    assert sessions["primary"]["calendar"] == "XNYS"
    assert sessions["primary"]["nominal_open"] == "09:30"
    assert sessions["primary"]["nominal_close"] == "16:00"
    assert sessions["overnight_negative_control"]["enabled"] is True
    assert (
        sessions["overnight_negative_control"][
            "may_select_or_replace_primary_parameters"
        ]
        is False
    )
    assert (
        protocol["design"]["state_model_comparison"]["pnl_selection_prohibited"]
        is True
    )
    assert protocol["design"]["state_model_comparison"]["coherence_threshold"] is None
    assert protocol["design"]["magnitude_coordinates"]["joint_intensity"] == (
        "geometric_mean"
    )
    assert protocol["design"]["magnitude_coordinates"]["magnitude_balance"] == (
        "normalized_difference"
    )
    scale = protocol["design"]["magnitude_coordinates"]["historical_scale"]
    assert scale["estimator"] == "same_session_slot_mad"
    assert scale["lookback_eligible_sessions"] == 63
    assert scale["include_current_session"] is False
    assert scale["epsilon_floor"] is None
    assert protocol["design"]["state_model_comparison"]["m0_predictors"][-1] == (
        "common_direction"
    )
    assert protocol["research"]["hypotheses"][1]["name"] == (
        "magnitude_conditioned_persistence"
    )
    current_iteration = protocol["data"]["current_iteration"]
    assert current_iteration["mode"] == "development_only"
    assert current_iteration["complete_primary_sessions_before_warmup"] == 458
    assert current_iteration["complete_overnight_sessions_before_warmup"] == 551
    assert current_iteration["pre_etp_sample_available"] is False
    assert current_iteration["pristine_final_holdout_available"] is False
    assert current_iteration["confirmatory_claims_permitted"] is False

    multiplicity = protocol["governance"]["multiplicity"]
    assert multiplicity["familywise_confirmatory_error_control"] == "not_claimed"
    assert multiplicity["secondary_may_rescue_primary"] is False
    assert multiplicity["future_confirmatory_procedure"] == "new_protocol_required"


def test_frozen_protocol_rejects_unresolved_holdout() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    protocol["status"] = "frozen"
    protocol["governance"]["protocol_frozen"] = True

    with pytest.raises(ProtocolError, match="unresolved values"):
        validate_protocol(protocol)


def test_completed_record_cannot_be_relabelled_as_preregistered() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    protocol["governance"]["preregistered"] = True

    with pytest.raises(ProtocolError, match="was not preregistered"):
        validate_protocol(protocol)


def test_secondary_results_cannot_rescue_primary_result() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    protocol["governance"]["multiplicity"]["secondary_may_rescue_primary"] = True

    with pytest.raises(ProtocolError, match="Multiplicity governance has drifted"):
        validate_protocol(protocol)


def test_duplicate_hypothesis_ids_are_rejected() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    protocol["research"]["hypotheses"].append(
        {"id": "H1", "name": "duplicate", "role": "secondary"}
    )

    with pytest.raises(ProtocolError, match="must be unique"):
        validate_protocol(protocol)


def test_coherence_cannot_include_magnitude() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    protocol["design"]["coherence_excludes_magnitude"] = False

    with pytest.raises(ProtocolError, match="Coherence must exclude"):
        validate_protocol(protocol)


def test_primary_design_cannot_silently_add_wicks() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    protocol["design"]["primary_uses_wicks_or_range"] = True

    with pytest.raises(ProtocolError, match="Wicks and high-low range"):
        validate_protocol(protocol)


def test_coherence_scales_cannot_drift() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    protocol["design"]["coherence_measure"]["scales_minutes"] = [15, 30]

    with pytest.raises(ProtocolError, match="exactly 15, 30, and 60"):
        validate_protocol(protocol)


def test_state_research_cannot_set_strategy_threshold() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    protocol["design"]["state_model_comparison"]["coherence_threshold"] = 0.7

    with pytest.raises(ProtocolError, match="cannot be set before strategy"):
        validate_protocol(protocol)


def test_one_minute_robustness_cannot_be_conditionally_skipped() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    protocol["design"]["run_robustness_regardless_of_primary_result"] = False

    with pytest.raises(ProtocolError, match="robustness analysis is mandatory"):
        validate_protocol(protocol)


def test_primary_economic_horizon_cannot_drift() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    protocol["design"]["primary_horizon_minutes"] = 1

    with pytest.raises(ProtocolError, match="must be five minutes"):
        validate_protocol(protocol)


def test_one_minute_economic_primary_must_span_five_bars() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    protocol["design"]["economic_return"]["robustness_one_minute_bars"] = 1

    with pytest.raises(ProtocolError, match="must span five future bars"):
        validate_protocol(protocol)


def test_secondary_horizon_cannot_replace_primary() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    protocol["design"]["economic_return"]["secondary_may_replace_primary"] = True

    with pytest.raises(ProtocolError, match="cannot replace"):
        validate_protocol(protocol)


def test_incomplete_primary_bar_cannot_be_accepted() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    protocol["design"]["bar_construction"]["incomplete_bin_policy"] = "accept"

    with pytest.raises(ProtocolError, match="must be ineligible"):
        validate_protocol(protocol)


def test_primary_bar_ohlcv_rules_cannot_drift() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    protocol["design"]["bar_construction"]["close"] = "mean"

    with pytest.raises(ProtocolError, match="registered OHLCV aggregation"):
        validate_protocol(protocol)


def test_joint_intensity_definition_cannot_drift() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    protocol["design"]["magnitude_coordinates"]["joint_intensity"] = "mean"

    with pytest.raises(ProtocolError, match="must use the geometric mean"):
        validate_protocol(protocol)


def test_m1_must_represent_signed_and_absolute_balance() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    protocol["design"]["state_model_comparison"]["m1_additional_predictors"] = [
        "joint_intensity",
        "magnitude_balance",
    ]

    with pytest.raises(ProtocolError, match="must add joint intensity"):
        validate_protocol(protocol)


def test_historical_scale_cannot_use_standard_deviation() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    scale = protocol["design"]["magnitude_coordinates"]["historical_scale"]
    scale["estimator"] = "standard_deviation"

    with pytest.raises(ProtocolError, match="must use same-slot MAD"):
        validate_protocol(protocol)


def test_historical_scale_cannot_include_current_session() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    scale = protocol["design"]["magnitude_coordinates"]["historical_scale"]
    scale["include_current_session"] = True

    with pytest.raises(ProtocolError, match="cannot enter its own"):
        validate_protocol(protocol)


def test_historical_scale_lookback_cannot_drift() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    scale = protocol["design"]["magnitude_coordinates"]["historical_scale"]
    scale["lookback_eligible_sessions"] = 20

    with pytest.raises(ProtocolError, match="must use 63 eligible sessions"):
        validate_protocol(protocol)


def test_dataset_warmup_must_match_scale_lookback() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    protocol["data"]["minimum_pre_sample_warmup_sessions"] = 20

    with pytest.raises(ProtocolError, match="63-session warm-up"):
        validate_protocol(protocol)


def test_primary_target_cannot_cross_official_close() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    primary = protocol["design"]["session_scope"]["primary"]
    primary["target_must_end_by_official_close"] = False

    with pytest.raises(ProtocolError, match="must end by the official close"):
        validate_protocol(protocol)


def test_overnight_control_cannot_be_skipped() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    overnight = protocol["design"]["session_scope"]["overnight_negative_control"]
    overnight["required_regardless_of_primary_result"] = False

    with pytest.raises(ProtocolError, match="overnight negative control is mandatory"):
        validate_protocol(protocol)


def test_overnight_result_cannot_replace_primary() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    overnight = protocol["design"]["session_scope"]["overnight_negative_control"]
    overnight["may_select_or_replace_primary_parameters"] = True

    with pytest.raises(ProtocolError, match="cannot select primary parameters"):
        validate_protocol(protocol)


def test_current_data_cannot_be_relabelled_as_confirmatory() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    protocol["data"]["current_iteration"]["confirmatory_claims_permitted"] = True

    with pytest.raises(ProtocolError, match="Confirmatory claims are prohibited"):
        validate_protocol(protocol)
