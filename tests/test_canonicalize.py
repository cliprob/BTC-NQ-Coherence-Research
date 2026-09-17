from __future__ import annotations

import pandas as pd

from btc_nq_coherence.canonicalize import _evaluate_sessions


def test_incomplete_session_is_excluded_without_forward_fill() -> None:
    expected = pd.date_range(
        "2024-03-07T14:30:00Z", periods=3, freq="1min", tz="UTC"
    )
    nq_index = expected.delete(1)
    btc_index = expected

    summary, timestamp_map = _evaluate_sessions(
        role="primary",
        expected_by_session=[("2024-03-07", expected)],
        nq_index=nq_index,
        btc_index=btc_index,
        roll_dates=set(),
    )

    assert summary.eligible_sessions == 0
    assert summary.excluded_sessions[0].missing_nq_minutes == 1
    assert timestamp_map == {}


def test_roll_session_is_excluded_even_when_minutes_are_complete() -> None:
    expected = pd.date_range(
        "2024-03-07T14:30:00Z", periods=3, freq="1min", tz="UTC"
    )

    summary, timestamp_map = _evaluate_sessions(
        role="primary",
        expected_by_session=[("2024-03-07", expected)],
        nq_index=expected,
        btc_index=expected,
        roll_dates={"2024-03-07"},
    )

    assert summary.eligible_sessions == 0
    assert summary.excluded_sessions[0].reasons == (
        "contract_transition_session",
    )
    assert timestamp_map == {}


def test_complete_non_roll_session_is_eligible() -> None:
    expected = pd.date_range(
        "2024-03-07T14:30:00Z", periods=3, freq="1min", tz="UTC"
    )

    summary, timestamp_map = _evaluate_sessions(
        role="primary",
        expected_by_session=[("2024-03-07", expected)],
        nq_index=expected,
        btc_index=expected,
        roll_dates=set(),
    )

    assert summary.eligible_sessions == 1
    assert summary.eligible_minutes == 3
    assert set(timestamp_map.values()) == {"2024-03-07"}

