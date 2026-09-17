from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from btc_nq_coherence.state_models import (
    M0_FEATURES,
    M1_FEATURES,
    StateModelError,
    build_inner_folds,
    build_outer_folds,
    calibration_table,
    fit_probability_model,
    paired_session_interval,
    tune_regularization,
    validate_state_model_config,
)

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _model_rows(session_count: int = 14, rows_per_session: int = 4) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    timestamps: list[pd.Timestamp] = []
    for session in range(session_count):
        session_date = f"2024-01-{session + 2:02d}"
        for row_number in range(rows_per_session):
            value = float(session * rows_per_session + row_number)
            target = int((session + row_number) % 3 != 0)
            rows.append(
                {
                    "analysis_session_date": session_date,
                    "next_bar_agreement_label": target,
                    "coherence_15m": (value % 5) / 5,
                    "coherence_30m": (value % 7) / 7,
                    "coherence_60m": (value % 11) / 11,
                    "common_direction": 1 if row_number % 2 else -1,
                    "joint_intensity": 0.1 + value / 100,
                    "magnitude_balance": (row_number - 1.5) / 2,
                    "absolute_magnitude_balance": abs((row_number - 1.5) / 2),
                }
            )
            timestamps.append(
                pd.Timestamp(session_date, tz="UTC") + pd.Timedelta(minutes=row_number)
            )
    return pd.DataFrame(rows, index=timestamps)


def test_repository_model_config_is_valid_and_cannot_drift() -> None:
    config = yaml.safe_load((ROOT / "configs" / "state_models.yaml").read_text())
    validate_state_model_config(config)

    config["models"]["m1"]["predictors"].append("future_return")
    with pytest.raises(StateModelError, match="M1 predictors"):
        validate_state_model_config(config)


def test_outer_folds_are_expanding_purged_and_non_overlapping() -> None:
    sessions = [f"s{index:02d}" for index in range(13)]
    folds = build_outer_folds(
        sessions,
        initial_training_sessions=4,
        validation_sessions=2,
        step_sessions=2,
        purge_sessions=1,
    )

    assert len(folds) == 4
    assert folds[0].train_sessions == ("s00", "s01", "s02", "s03")
    assert folds[0].purge_sessions == ("s04",)
    assert folds[0].validation_sessions == ("s05", "s06")
    assert folds[-1].validation_sessions == ("s11", "s12")
    assert set(folds[0].train_sessions).isdisjoint(folds[0].validation_sessions)


def test_inner_folds_use_only_outer_training_history() -> None:
    training = tuple(f"s{index:02d}" for index in range(10))
    folds = build_inner_folds(
        training, fold_count=2, validation_sessions=2, purge_sessions=1
    )

    assert folds[0].train_sessions[-1] == "s04"
    assert folds[0].purge_sessions == ("s05",)
    assert folds[0].validation_sessions == ("s06", "s07")
    assert folds[1].validation_sessions == ("s08", "s09")


def test_validation_values_cannot_change_fold_fitted_scaler() -> None:
    frame = _model_rows(session_count=4)
    training = frame.loc[frame["analysis_session_date"].isin(["2024-01-02", "2024-01-03"])]
    validation = frame.loc[frame["analysis_session_date"].eq("2024-01-04")].copy()
    pipeline, original = fit_probability_model(
        training,
        validation,
        features=M1_FEATURES,
        c_value=0.1,
        max_iterations=500,
    )
    validation.iloc[-1, validation.columns.get_loc("joint_intensity")] = 1_000_000.0
    changed = pipeline.predict_proba(validation[list(M1_FEATURES)])[:, 1]

    assert float(changed[0]) == pytest.approx(original[0])
    scaler = pipeline.named_steps["scaler"]
    assert float(scaler.mean_[4]) == pytest.approx(training["joint_intensity"].mean())


def test_outer_validation_targets_cannot_select_regularization() -> None:
    frame = _model_rows(session_count=13)
    sessions = sorted(frame["analysis_session_date"].unique())
    outer = build_outer_folds(
        sessions,
        initial_training_sessions=8,
        validation_sessions=2,
        step_sessions=2,
        purge_sessions=1,
    )[0]
    selected, _ = tune_regularization(
        frame,
        outer,
        resolution_minutes=5,
        model_name="m0",
        features=M0_FEATURES,
        c_grid=[0.01, 0.1],
        inner_fold_count=2,
        inner_validation_sessions=2,
        inner_purge_sessions=1,
        max_iterations=500,
        run_id="test",
    )
    changed = frame.copy()
    validation_mask = changed["analysis_session_date"].isin(outer.validation_sessions)
    changed.loc[validation_mask, "next_bar_agreement_label"] = 1 - changed.loc[
        validation_mask, "next_bar_agreement_label"
    ]
    selected_after_change, _ = tune_regularization(
        changed,
        outer,
        resolution_minutes=5,
        model_name="m0",
        features=M0_FEATURES,
        c_grid=[0.01, 0.1],
        inner_fold_count=2,
        inner_validation_sessions=2,
        inner_purge_sessions=1,
        max_iterations=500,
        run_id="test",
    )

    assert selected_after_change == selected


def test_paired_session_interval_is_deterministic() -> None:
    sessions = ["a", "a", "b", "b", "c", "c"]
    differences = [0.1, -0.1, 0.2, 0.1, -0.3, -0.2]
    first = paired_session_interval(
        sessions,
        differences,
        replications=1000,
        confidence_level=0.95,
        seed=11,
    )
    second = paired_session_interval(
        sessions,
        differences,
        replications=1000,
        confidence_level=0.95,
        seed=11,
    )

    assert first == second


def test_calibration_table_retains_empty_fixed_width_bins() -> None:
    oof = pd.DataFrame(
        {
            "resolution_minutes": 5,
            "next_bar_agreement_label": [0, 1],
            "benchmark_probability": [0.5, 0.5],
            "m0_probability": [0.2, 0.8],
            "m1_probability": [0.3, 0.7],
        }
    )
    table = calibration_table(oof, bin_count=10)

    assert len(table) == 30
    assert table["event_count"].eq(0).any()


def test_committed_state_model_artifacts_match_manifest() -> None:
    manifest = json.loads(
        (ROOT / "data" / "registry" / "state_model_manifest.json").read_text()
    )
    report_directory = ROOT / "reports" / "development"

    for file_name, metadata in manifest["committed_artifacts"].items():
        assert metadata["committed"] is True
        assert _sha256(report_directory / file_name) == metadata["sha256"]
