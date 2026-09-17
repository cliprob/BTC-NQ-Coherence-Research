from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from btc_nq_coherence.features import (
    FeatureError,
    _causal_same_slot_mad,
    aggregate_five_minute,
    compute_features,
    validate_feature_config,
)

ROOT = Path(__file__).resolve().parents[1]


def _minute_context(periods: int = 15) -> pd.DataFrame:
    index = pd.date_range("2024-03-07T14:30:00Z", periods=periods, freq="1min")
    base = np.arange(periods, dtype=float)
    return pd.DataFrame(
        {
            "nq_open": 100.0 + base,
            "nq_high": 101.5 + base,
            "nq_low": 99.5 + base,
            "nq_close": 101.0 + base,
            "nq_volume": 10.0,
            "nq_contract": 202403,
            "btc_open": 200.0 + base,
            "btc_high": 202.5 + base,
            "btc_low": 199.5 + base,
            "btc_close": 202.0 + base,
            "btc_volume": 20.0,
            "analysis_session_date": "2024-03-07",
            "is_signal_bar": True,
            "source_valid": True,
        },
        index=index,
    )


def test_five_minute_ohlcv_aggregation() -> None:
    aggregated = aggregate_five_minute(_minute_context(5))

    assert len(aggregated) == 1
    row = aggregated.iloc[0]
    assert row["nq_open"] == 100.0
    assert row["nq_high"] == 105.5
    assert row["nq_low"] == 99.5
    assert row["nq_close"] == 105.0
    assert row["nq_volume"] == 50.0
    assert bool(row["source_valid"]) is True


def test_incomplete_five_minute_bin_is_ineligible() -> None:
    context = _minute_context(5).drop(
        pd.Timestamp("2024-03-07T14:32:00Z")
    )
    aggregated = aggregate_five_minute(context)

    assert bool(aggregated.iloc[0]["source_valid"]) is False
    assert math.isnan(float(aggregated.iloc[0]["nq_open"]))


def test_same_slot_mad_uses_only_prior_values() -> None:
    index = pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC")
    values = pd.Series([1.0, 2.0, 4.0, 8.0, 10_000.0], index=index)

    original = _causal_same_slot_mad(values, lookback=3, constant=1.0)
    changed = values.copy()
    changed.iloc[-1] = -10_000.0
    after_future_change = _causal_same_slot_mad(changed, lookback=3, constant=1.0)

    assert original.iloc[:4].equals(after_future_change.iloc[:4])
    assert math.isnan(float(original.iloc[2]))
    assert original.iloc[3] == 1.0
    assert original.iloc[4] == 2.0


def test_coherence_uses_body_direction_not_magnitude() -> None:
    bars = _minute_context(3)
    bars.loc[bars.index[1], "btc_close"] = bars.loc[bars.index[1], "btc_open"] - 1
    features = compute_features(
        bars,
        bar_minutes=1,
        coherence_scales_minutes=(3,),
        scale_lookback_sessions=1,
        mad_constant=1.0,
    )

    assert features["direction_agreement"].tolist() == [1.0, -1.0, 1.0]
    assert features.iloc[-1]["coherence_3m"] == 1 / 3


def test_future_session_change_does_not_change_prior_features() -> None:
    indexes = pd.DatetimeIndex(
        [
            "2024-03-07T14:30:00Z",
            "2024-03-08T14:30:00Z",
            "2024-03-11T13:30:00Z",
        ]
    )
    bars = _minute_context(3)
    bars.index = indexes
    bars["analysis_session_date"] = ["2024-03-07", "2024-03-08", "2024-03-11"]
    bars["btc_close"] = [201.0, 203.0, 205.0]
    bars["nq_close"] = [101.0, 103.0, 105.0]

    original = compute_features(
        bars,
        bar_minutes=1,
        coherence_scales_minutes=(1,),
        scale_lookback_sessions=2,
        mad_constant=1.0,
    )
    changed = bars.copy()
    changed.loc[indexes[-1], ["btc_close", "nq_close"]] = [400.0, 250.0]
    recomputed = compute_features(
        changed,
        bar_minutes=1,
        coherence_scales_minutes=(1,),
        scale_lookback_sessions=2,
        mad_constant=1.0,
    )

    columns = [
        "btc_body_scale",
        "nq_body_scale",
        "coherence_1m",
        "joint_intensity",
        "magnitude_balance",
    ]
    pd.testing.assert_frame_equal(original.iloc[:2][columns], recomputed.iloc[:2][columns])
    assert original.iloc[0]["feature_available_timestamp_utc"] == (
        indexes[0] + pd.Timedelta(minutes=1)
    )


def test_repository_feature_config_is_valid_and_cannot_drift() -> None:
    config = yaml.safe_load((ROOT / "configs" / "features.yaml").read_text())
    validate_feature_config(config)

    config["historical_scale"]["lookback_eligible_sessions"] = 20
    with pytest.raises(FeatureError, match="must use 63 eligible sessions"):
        validate_feature_config(config)
