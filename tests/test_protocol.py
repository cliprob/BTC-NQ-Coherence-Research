from pathlib import Path

import pytest

from btc_nq_coherence.protocol import ProtocolError, load_protocol, validate_protocol

ROOT = Path(__file__).resolve().parents[1]


def test_repository_protocol_is_valid_draft() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")

    assert protocol["status"] == "draft"
    assert protocol["governance"]["protocol_frozen"] is False
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
    assert protocol["design"]["state_model_comparison"]["m0_predictors"][-1] == (
        "common_direction"
    )
    assert protocol["research"]["hypotheses"][1]["name"] == (
        "magnitude_conditioned_persistence"
    )


def test_frozen_protocol_rejects_unresolved_holdout() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    protocol["status"] = "frozen"
    protocol["governance"]["protocol_frozen"] = True

    with pytest.raises(ProtocolError, match="unresolved values"):
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
