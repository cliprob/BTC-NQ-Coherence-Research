from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from btc_nq_coherence.return_models import (
    CROSS_MARKET_FEATURES,
    NQ_ONLY_FEATURES,
    TARGET,
    ReturnModelError,
    derive_return_features,
    fit_return_model,
    tune_alpha,
    validate_return_model_config,
)
from btc_nq_coherence.state_models import build_outer_folds

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _raw_session(start: str, periods: int = 70) -> pd.DataFrame:
    index = pd.date_range(start, periods=periods, freq="1min")
    values = [100.0 + number * 0.1 for number in range(periods)]
    return pd.DataFrame(
        {
            "analysis_session_date": str(index[0].date()),
            "nq_close": values,
            "btc_close": [value * 2 for value in values],
            "nq_direction": [1 if number % 2 == 0 else -1 for number in range(periods)],
        },
        index=index,
    )


def _model_rows(session_count: int = 13, rows_per_session: int = 4) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    timestamps: list[pd.Timestamp] = []
    for session in range(session_count):
        session_date = f"2024-01-{session + 2:02d}"
        for row_number in range(rows_per_session):
            value = float(session * rows_per_session + row_number)
            row: dict[str, object] = {
                "analysis_session_date": session_date,
                TARGET: (value % 9) - 4.0,
            }
            for feature_number, feature in enumerate(CROSS_MARKET_FEATURES):
                row[feature] = value / 100 + feature_number / 10
            rows.append(row)
            timestamps.append(
                pd.Timestamp(session_date, tz="UTC") + pd.Timedelta(minutes=row_number)
            )
    return pd.DataFrame(rows, index=timestamps)


def test_repository_return_model_config_is_valid_and_cannot_drift() -> None:
    config = yaml.safe_load((ROOT / "configs" / "return_models.yaml").read_text())
    validate_return_model_config(config)

    config["population"]["target_winsorization"] = "global"
    with pytest.raises(ReturnModelError, match="population or target"):
        validate_return_model_config(config)


def test_momentum_features_are_causal_and_reset_at_session_boundary() -> None:
    first = _raw_session("2024-03-07T14:30:00Z")
    second = _raw_session("2024-03-08T14:30:00Z")
    frame = pd.concat([first, second])
    derived = derive_return_features(frame, bar_minutes=1)
    original = float(derived.iloc[10]["nq_aligned_momentum_5m"])

    changed = frame.copy()
    changed.loc[changed.index[-1], "nq_close"] = 1_000_000.0
    changed_derived = derive_return_features(changed, bar_minutes=1)

    assert float(changed_derived.iloc[10]["nq_aligned_momentum_5m"]) == pytest.approx(
        original
    )
    assert pd.isna(changed_derived.iloc[len(first)]["nq_aligned_momentum_5m"])
    assert pd.isna(changed_derived.iloc[len(first) + 59]["nq_aligned_momentum_60m"])
    assert pd.notna(changed_derived.iloc[len(first) + 60]["nq_aligned_momentum_60m"])


def test_validation_values_cannot_change_fold_fitted_scaler() -> None:
    frame = _model_rows(session_count=4)
    training = frame.loc[frame["analysis_session_date"].isin(["2024-01-02", "2024-01-03"])]
    validation = frame.loc[frame["analysis_session_date"].eq("2024-01-04")].copy()
    pipeline, original = fit_return_model(
        training,
        validation,
        features=NQ_ONLY_FEATURES,
        alpha=1.0,
    )
    validation.iloc[-1, validation.columns.get_loc("nq_magnitude")] = 1_000_000.0
    changed = pipeline.predict(validation[list(NQ_ONLY_FEATURES)])

    assert float(changed[0]) == pytest.approx(original[0])
    scaler = pipeline.named_steps["scaler"]
    assert float(scaler.mean_[1]) == pytest.approx(training["nq_magnitude"].mean())


def test_outer_validation_targets_cannot_select_alpha() -> None:
    frame = _model_rows()
    sessions = sorted(frame["analysis_session_date"].unique())
    outer = build_outer_folds(
        sessions,
        initial_training_sessions=8,
        validation_sessions=2,
        step_sessions=2,
        purge_sessions=1,
    )[0]
    selected, _ = tune_alpha(
        frame,
        outer,
        resolution_minutes=5,
        model_name="nq_only",
        features=NQ_ONLY_FEATURES,
        alpha_grid=[0.1, 1.0],
        inner_fold_count=2,
        inner_validation_sessions=2,
        inner_purge_sessions=1,
        run_id="test",
    )
    changed = frame.copy()
    validation_mask = changed["analysis_session_date"].isin(outer.validation_sessions)
    changed.loc[validation_mask, TARGET] *= -10_000
    selected_after_change, _ = tune_alpha(
        changed,
        outer,
        resolution_minutes=5,
        model_name="nq_only",
        features=NQ_ONLY_FEATURES,
        alpha_grid=[0.1, 1.0],
        inner_fold_count=2,
        inner_validation_sessions=2,
        inner_purge_sessions=1,
        run_id="test",
    )

    assert selected_after_change == selected


def test_committed_return_model_artifacts_match_manifest() -> None:
    manifest = json.loads(
        (ROOT / "data" / "registry" / "return_model_manifest.json").read_text()
    )
    report_directory = ROOT / "reports" / "development"

    for file_name, metadata in manifest["committed_artifacts"].items():
        assert metadata["committed"] is True
        assert _sha256(report_directory / file_name) == metadata["sha256"]
