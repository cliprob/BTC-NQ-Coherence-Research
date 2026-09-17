from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml

from btc_nq_coherence.overnight_features import (
    OvernightFeatureError,
    build_overnight_context,
    validate_overnight_feature_config,
)

ROOT = Path(__file__).resolve().parents[1]


def _canonical_overnight(periods: int = 930) -> pd.DataFrame:
    index = pd.date_range("2024-03-07T23:00:00Z", periods=periods, freq="1min")
    base = pd.Series(range(periods), index=index, dtype=float)
    return pd.DataFrame(
        {
            "overnight_session_date": "2024-03-08",
            "eligible_overnight_control": True,
            "nq_open": 18_000.0 + base,
            "nq_high": 18_001.0 + base,
            "nq_low": 17_999.0 + base,
            "nq_close": 18_000.5 + base,
            "nq_contract": 202406,
            "btc_open": 60_000.0 + base,
            "btc_high": 60_002.0 + base,
            "btc_low": 59_999.0 + base,
            "btc_close": 60_001.0 + base,
        },
        index=index,
    )


def test_repository_overnight_feature_config_is_frozen() -> None:
    config = yaml.safe_load((ROOT / "configs" / "overnight_features.yaml").read_text())
    validate_overnight_feature_config(config)

    config["session_context"]["session_end"] = "10:00"
    with pytest.raises(OvernightFeatureError, match="context has drifted"):
        validate_overnight_feature_config(config)


def test_overnight_context_requires_exact_complete_session() -> None:
    context = build_overnight_context(_canonical_overnight())

    assert len(context) == 930
    assert context["analysis_session_date"].eq("2024-03-08").all()
    assert context["is_signal_bar"].all()

    with pytest.raises(OvernightFeatureError, match="930 minutes"):
        build_overnight_context(_canonical_overnight(929))

