from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest
import yaml

from btc_nq_coherence.outcomes import (
    OutcomeError,
    build_outcomes,
    validate_outcome_config,
)

ROOT = Path(__file__).resolve().parents[1]


def _bars() -> pd.DataFrame:
    index = pd.date_range("2024-03-07T14:30:00Z", periods=5, freq="5min")
    return pd.DataFrame(
        {
            "feature_available_timestamp_utc": index + pd.Timedelta(minutes=5),
            "analysis_session_date": "2024-03-07",
            "bar_minutes": 5,
            "nq_open": [100.0, 101.0, 103.0, 102.0, 104.0],
            "direction_agreement": [1.0, 1.0, 1.0, -1.0, 1.0],
            "common_direction": [1.0, 1.0, 1.0, math.nan, -1.0],
            "feature_ready": True,
        },
        index=index,
    )


def test_return_uses_next_open_then_horizon_open() -> None:
    outcomes = build_outcomes(_bars(), bar_minutes=5, horizons_minutes=(5,))

    expected = math.log(103.0 / 101.0)
    assert outcomes.iloc[0]["nq_log_return_5m"] == pytest.approx(expected)
    assert outcomes.iloc[0]["signed_nq_log_return_5m"] == pytest.approx(expected)
    assert outcomes.iloc[0]["outcome_entry_timestamp_utc"] == pd.Timestamp(
        "2024-03-07T14:35:00Z"
    )


def test_return_crossing_session_end_is_ineligible() -> None:
    outcomes = build_outcomes(_bars(), bar_minutes=5, horizons_minutes=(5,))

    assert math.isnan(float(outcomes.iloc[-2]["nq_log_return_5m"]))
    assert bool(outcomes.iloc[-2]["outcome_ready_5m"]) is False


def test_persistence_duration_and_censoring() -> None:
    outcomes = build_outcomes(_bars(), bar_minutes=5, horizons_minutes=(5,))

    assert outcomes.iloc[0]["next_bar_agreement_label"] == 1.0
    assert outcomes.iloc[0]["persistence_run_bars"] == 2.0
    assert bool(outcomes.iloc[0]["persistence_end_observed"]) is True
    assert outcomes.iloc[2]["persistence_run_bars"] == 0.0
    assert bool(outcomes.iloc[2]["persistence_end_observed"]) is True
    assert outcomes.iloc[-1]["persistence_run_bars"] == 0.0
    assert bool(outcomes.iloc[-1]["persistence_right_censored"]) is True


def test_gap_right_censors_persistence_instead_of_observing_decay() -> None:
    bars = _bars().drop(_bars().index[2])
    outcomes = build_outcomes(bars, bar_minutes=5, horizons_minutes=(5,))

    assert outcomes.iloc[1]["persistence_run_bars"] == 0.0
    assert bool(outcomes.iloc[1]["persistence_right_censored"]) is True


def test_feature_availability_must_match_event_bar_close() -> None:
    bars = _bars()
    bars.loc[bars.index[0], "feature_available_timestamp_utc"] = bars.index[0]

    with pytest.raises(OutcomeError, match="event-bar close"):
        build_outcomes(bars, bar_minutes=5, horizons_minutes=(5,))


def test_repository_outcome_config_is_valid_and_cannot_drift() -> None:
    config = yaml.safe_load((ROOT / "configs" / "outcomes.yaml").read_text())
    validate_outcome_config(config)

    config["timing"]["entry_price"] = "event_close"
    with pytest.raises(OutcomeError, match="timing differs"):
        validate_outcome_config(config)
