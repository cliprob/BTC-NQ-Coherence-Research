"""Purged walk-forward comparison of coherence-only and magnitude state models."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]
import yaml
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
from sklearn.metrics import brier_score_loss, log_loss  # type: ignore[import-untyped]
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]


class StateModelError(ValueError):
    """Raised when model evaluation would violate the registered design."""


M0_FEATURES = ("coherence_15m", "coherence_30m", "coherence_60m", "common_direction")
M1_FEATURES = (
    *M0_FEATURES,
    "joint_intensity",
    "magnitude_balance",
    "absolute_magnitude_balance",
)


@dataclass(frozen=True)
class SessionFold:
    """One chronological train/purge/validation split."""

    fold: int
    train_sessions: tuple[str, ...]
    purge_sessions: tuple[str, ...]
    validation_sessions: tuple[str, ...]


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        payload = yaml.safe_load(stream)
    if not isinstance(payload, dict):
        raise StateModelError(f"YAML root must be a mapping: {path}")
    return payload


def validate_state_model_config(config: dict[str, Any]) -> None:
    """Prevent silent changes to models, folds, or evidence rules."""
    if config.get("schema_version") != 1 or config.get("status") != "development_only":
        raise StateModelError("State-model config must remain schema 1 and development-only.")
    population = config.get("population", {})
    if population != {
        "feature_ready": True,
        "current_direction_agreement": 1,
        "target": "next_bar_agreement_label",
    }:
        raise StateModelError("State-model population or target has drifted.")
    models = config.get("models", {})
    if models.get("m0", {}).get("predictors") != list(M0_FEATURES):
        raise StateModelError("M0 predictors differ from the protocol.")
    if models.get("m1", {}).get("predictors") != list(M1_FEATURES):
        raise StateModelError("M1 predictors differ from the protocol.")
    if models.get("preprocessing") != "standard_scaler_fit_on_training_fold_only":
        raise StateModelError("Preprocessing must be fitted inside each training fold.")
    if models.get("penalty") != "l2" or models.get("solver") != "lbfgs":
        raise StateModelError("Only the registered L2 logistic estimator is permitted.")
    if models.get("regularization_c_grid") != [0.01, 0.1, 1.0, 10.0]:
        raise StateModelError("Regularization grid has drifted.")
    walk = config.get("walk_forward", {})
    expected_walk = {
        "session_order": "chronological",
        "initial_training_sessions": 130,
        "validation_sessions": 22,
        "step_sessions": 22,
        "purge_sessions": 1,
        "inner_validation_folds": 3,
        "inner_validation_sessions": 22,
        "inner_purge_sessions": 1,
        "inner_selection_aggregation": "event_weighted_oof_brier",
        "partial_final_fold": "reject",
    }
    if walk != expected_walk:
        raise StateModelError("Walk-forward specification has drifted.")
    evaluation = config.get("evaluation", {})
    if evaluation.get("primary_metric") != "brier_score":
        raise StateModelError("Brier score must remain the primary model metric.")
    if evaluation.get("secondary_metric") != "log_loss":
        raise StateModelError("Log loss must remain the secondary model metric.")
    if evaluation.get("resolutions_minutes") != [5, 1]:
        raise StateModelError("Both five- and one-minute specifications are required.")
    if evaluation.get("maximum_ece_deterioration") != 0.01:
        raise StateModelError("ECE deterioration tolerance has drifted.")
    uncertainty = config.get("uncertainty", {})
    if uncertainty.get("method") != "paired_analysis_session_block_bootstrap":
        raise StateModelError("Loss differences require paired session-block bootstrap.")
    if uncertainty.get("confidence_level") != 0.95:
        raise StateModelError("Confidence level must remain 95%.")
    if int(uncertainty.get("replications", 0)) < 1000:
        raise StateModelError("At least 1,000 bootstrap replications are required.")


def load_model_population(path: Path, expected_hash: str) -> pd.DataFrame:
    """Load, verify, and select feature-ready current-agreement observations."""
    if not path.is_file() or _hash_file(path) != expected_hash:
        raise StateModelError(f"Outcome artifact identity mismatch: {path}")
    frame = pd.read_csv(path)
    required = {
        "timestamp_utc",
        "analysis_session_date",
        "feature_ready",
        "direction_agreement",
        "state_model_eligible",
        "next_bar_agreement_label",
        *M1_FEATURES,
    }
    missing = required.difference(frame.columns)
    if missing:
        raise StateModelError(f"Outcome artifact is missing columns: {sorted(missing)}")
    frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True)
    frame = frame.set_index("timestamp_utc").sort_index()
    if frame.index.has_duplicates:
        raise StateModelError("Outcome timestamps must be unique.")
    ready = frame["feature_ready"].astype(str).str.lower().eq("true")
    eligible = frame["state_model_eligible"].astype(str).str.lower().eq("true")
    mask = (
        ready
        & eligible
        & frame["direction_agreement"].eq(1)
        & frame["next_bar_agreement_label"].isin([0, 1])
        & frame[list(M1_FEATURES)].notna().all(axis=1)
    )
    population = frame.loc[
        mask, ["analysis_session_date", "next_bar_agreement_label", *M1_FEATURES]
    ].copy()
    population["next_bar_agreement_label"] = population[
        "next_bar_agreement_label"
    ].astype(int)
    if population.empty:
        raise StateModelError("No eligible state-model observations remain.")
    return population


def build_outer_folds(
    sessions: list[str],
    *,
    initial_training_sessions: int,
    validation_sessions: int,
    step_sessions: int,
    purge_sessions: int,
) -> list[SessionFold]:
    """Build expanding chronological folds in whole-session units."""
    if validation_sessions != step_sessions:
        raise StateModelError("This registered design requires contiguous validation blocks.")
    remaining = len(sessions) - initial_training_sessions - purge_sessions
    if remaining <= 0 or remaining % validation_sessions:
        raise StateModelError("Session count does not support exact full validation folds.")
    folds: list[SessionFold] = []
    for fold_number in range(remaining // validation_sessions):
        validation_start = (
            initial_training_sessions + purge_sessions + fold_number * step_sessions
        )
        training_end = validation_start - purge_sessions
        validation_end = validation_start + validation_sessions
        folds.append(
            SessionFold(
                fold=fold_number,
                train_sessions=tuple(sessions[:training_end]),
                purge_sessions=tuple(sessions[training_end:validation_start]),
                validation_sessions=tuple(sessions[validation_start:validation_end]),
            )
        )
    return folds


def build_inner_folds(
    training_sessions: tuple[str, ...],
    *,
    fold_count: int,
    validation_sessions: int,
    purge_sessions: int,
) -> list[SessionFold]:
    """Use the trailing training history for nested expanding validation."""
    first_validation = len(training_sessions) - fold_count * validation_sessions
    if first_validation - purge_sessions <= 0:
        raise StateModelError("Outer training history is too short for inner validation.")
    folds: list[SessionFold] = []
    for fold_number in range(fold_count):
        validation_start = first_validation + fold_number * validation_sessions
        training_end = validation_start - purge_sessions
        validation_end = validation_start + validation_sessions
        folds.append(
            SessionFold(
                fold=fold_number,
                train_sessions=training_sessions[:training_end],
                purge_sessions=training_sessions[training_end:validation_start],
                validation_sessions=training_sessions[validation_start:validation_end],
            )
        )
    return folds


def _rows_for_sessions(frame: pd.DataFrame, sessions: tuple[str, ...]) -> pd.DataFrame:
    return frame.loc[frame["analysis_session_date"].isin(sessions)]


def _new_pipeline(c_value: float, max_iterations: int) -> Pipeline:
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    C=c_value,
                    l1_ratio=0.0,
                    solver="lbfgs",
                    max_iter=max_iterations,
                    random_state=0,
                ),
            ),
        ]
    )


def fit_probability_model(
    training: pd.DataFrame,
    validation: pd.DataFrame,
    *,
    features: tuple[str, ...],
    c_value: float,
    max_iterations: int,
) -> tuple[Pipeline, list[float]]:
    """Fit scaler and model on training rows only, then score validation rows."""
    target = "next_bar_agreement_label"
    if training[target].nunique() != 2:
        raise StateModelError("A training fold contains only one target class.")
    pipeline = _new_pipeline(c_value, max_iterations)
    pipeline.fit(training[list(features)], training[target])
    probabilities = pipeline.predict_proba(validation[list(features)])[:, 1]
    return pipeline, [float(value) for value in probabilities]


def _brier_values(targets: list[int], probabilities: list[float]) -> list[float]:
    return [
        (float(target) - probability) ** 2
        for target, probability in zip(targets, probabilities, strict=True)
    ]


def _log_loss_values(targets: list[int], probabilities: list[float]) -> list[float]:
    epsilon = 1e-15
    values: list[float] = []
    for target, probability in zip(targets, probabilities, strict=True):
        bounded = min(max(probability, epsilon), 1.0 - epsilon)
        values.append(
            -(target * math.log(bounded) + (1 - target) * math.log(1.0 - bounded))
        )
    return values


def tune_regularization(
    frame: pd.DataFrame,
    outer_fold: SessionFold,
    *,
    resolution_minutes: int,
    model_name: str,
    features: tuple[str, ...],
    c_grid: list[float],
    inner_fold_count: int,
    inner_validation_sessions: int,
    inner_purge_sessions: int,
    max_iterations: int,
    run_id: str,
) -> tuple[float, list[dict[str, Any]]]:
    """Select regularization from inner OOF Brier loss only."""
    inner_folds = build_inner_folds(
        outer_fold.train_sessions,
        fold_count=inner_fold_count,
        validation_sessions=inner_validation_sessions,
        purge_sessions=inner_purge_sessions,
    )
    scores: list[tuple[float, float, int, list[float]]] = []
    for c_value in c_grid:
        losses: list[float] = []
        fold_scores: list[float] = []
        for inner_fold in inner_folds:
            training = _rows_for_sessions(frame, inner_fold.train_sessions)
            validation = _rows_for_sessions(frame, inner_fold.validation_sessions)
            _, probabilities = fit_probability_model(
                training,
                validation,
                features=features,
                c_value=c_value,
                max_iterations=max_iterations,
            )
            targets = validation["next_bar_agreement_label"].astype(int).tolist()
            fold_losses = _brier_values(targets, probabilities)
            losses.extend(fold_losses)
            fold_scores.append(sum(fold_losses) / len(fold_losses))
        scores.append((sum(losses) / len(losses), c_value, len(losses), fold_scores))
    selected = min(scores, key=lambda item: (item[0], item[1]))[1]
    rows: list[dict[str, Any]] = []
    for mean_brier, c_value, event_count, fold_scores in scores:
        trial_key = (
            f"{run_id}|{resolution_minutes}|{outer_fold.fold}|{model_name}|{c_value}"
        )
        rows.append(
            {
                "trial_id": hashlib.sha256(trial_key.encode()).hexdigest()[:16],
                "run_id": run_id,
                "resolution_minutes": resolution_minutes,
                "outer_fold": outer_fold.fold,
                "model": model_name,
                "c_value": c_value,
                "inner_fold_count": len(inner_folds),
                "inner_event_count": event_count,
                "inner_oof_brier": mean_brier,
                "inner_fold_brier_json": json.dumps(fold_scores),
                "selected": c_value == selected,
            }
        )
    return selected, rows


def _model_coefficients(
    pipeline: Pipeline,
    features: tuple[str, ...],
    *,
    resolution_minutes: int,
    fold: int,
    model_name: str,
    c_value: float,
) -> list[dict[str, Any]]:
    estimator = pipeline.named_steps["model"]
    coefficients = estimator.coef_[0]
    rows = [
        {
            "resolution_minutes": resolution_minutes,
            "fold": fold,
            "model": model_name,
            "c_value": c_value,
            "term": feature,
            "standardized_coefficient": float(coefficient),
        }
        for feature, coefficient in zip(features, coefficients, strict=True)
    ]
    rows.append(
        {
            "resolution_minutes": resolution_minutes,
            "fold": fold,
            "model": model_name,
            "c_value": c_value,
            "term": "intercept",
            "standardized_coefficient": float(estimator.intercept_[0]),
        }
    )
    return rows


def _metric_row(
    targets: list[int], probabilities: list[float], model_name: str
) -> dict[str, float | str]:
    return {
        "model": model_name,
        "brier_score": float(brier_score_loss(targets, probabilities)),
        "log_loss": float(log_loss(targets, probabilities, labels=[0, 1])),
    }


def run_resolution(
    frame: pd.DataFrame,
    *,
    resolution_minutes: int,
    config: dict[str, Any],
    run_id: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate OOF predictions and audit artifacts for one resolution."""
    sessions = sorted(str(value) for value in frame["analysis_session_date"].unique())
    walk = config["walk_forward"]
    folds = build_outer_folds(
        sessions,
        initial_training_sessions=int(walk["initial_training_sessions"]),
        validation_sessions=int(walk["validation_sessions"]),
        step_sessions=int(walk["step_sessions"]),
        purge_sessions=int(walk["purge_sessions"]),
    )
    models = config["models"]
    c_grid = [float(value) for value in models["regularization_c_grid"]]
    max_iterations = int(models["max_iterations"])
    oof_parts: list[pd.DataFrame] = []
    fold_metric_rows: list[dict[str, Any]] = []
    coefficient_rows: list[dict[str, Any]] = []
    trial_rows: list[dict[str, Any]] = []
    for outer_fold in folds:
        training = _rows_for_sessions(frame, outer_fold.train_sessions)
        validation = _rows_for_sessions(frame, outer_fold.validation_sessions)
        predictions: dict[str, list[float]] = {
            "benchmark": [
                float(training["next_bar_agreement_label"].mean())
            ]
            * len(validation)
        }
        selected_values: dict[str, float] = {}
        for model_name, features in [("m0", M0_FEATURES), ("m1", M1_FEATURES)]:
            selected, trials = tune_regularization(
                frame,
                outer_fold,
                resolution_minutes=resolution_minutes,
                model_name=model_name,
                features=features,
                c_grid=c_grid,
                inner_fold_count=int(walk["inner_validation_folds"]),
                inner_validation_sessions=int(walk["inner_validation_sessions"]),
                inner_purge_sessions=int(walk["inner_purge_sessions"]),
                max_iterations=max_iterations,
                run_id=run_id,
            )
            trial_rows.extend(trials)
            selected_values[model_name] = selected
            pipeline, probabilities = fit_probability_model(
                training,
                validation,
                features=features,
                c_value=selected,
                max_iterations=max_iterations,
            )
            predictions[model_name] = probabilities
            coefficient_rows.extend(
                _model_coefficients(
                    pipeline,
                    features,
                    resolution_minutes=resolution_minutes,
                    fold=outer_fold.fold,
                    model_name=model_name,
                    c_value=selected,
                )
            )
        targets = validation["next_bar_agreement_label"].astype(int).tolist()
        for model_name, probabilities in predictions.items():
            row: dict[str, Any] = dict(
                _metric_row(targets, probabilities, model_name)
            )
            row.update(
                {
                    "resolution_minutes": resolution_minutes,
                    "fold": outer_fold.fold,
                    "train_session_start": outer_fold.train_sessions[0],
                    "train_session_end": outer_fold.train_sessions[-1],
                    "purge_session": outer_fold.purge_sessions[0],
                    "validation_session_start": outer_fold.validation_sessions[0],
                    "validation_session_end": outer_fold.validation_sessions[-1],
                    "train_session_count": len(outer_fold.train_sessions),
                    "validation_session_count": len(outer_fold.validation_sessions),
                    "train_event_count": len(training),
                    "validation_event_count": len(validation),
                    "selected_c": selected_values.get(model_name),
                }
            )
            fold_metric_rows.append(row)
        oof = validation[["analysis_session_date", "next_bar_agreement_label"]].copy()
        oof["resolution_minutes"] = resolution_minutes
        oof["fold"] = outer_fold.fold
        for model_name, probabilities in predictions.items():
            oof[f"{model_name}_probability"] = probabilities
        oof_parts.append(oof)
    oof_frame = pd.concat(oof_parts).sort_index()
    if oof_frame.index.has_duplicates:
        raise StateModelError("Outer validation folds overlap.")
    return (
        oof_frame,
        pd.DataFrame(fold_metric_rows),
        pd.DataFrame(coefficient_rows),
        pd.DataFrame(trial_rows),
    )


def calibration_table(oof: pd.DataFrame, bin_count: int) -> pd.DataFrame:
    """Create fixed-width reliability bins from OOF probabilities only."""
    rows: list[dict[str, Any]] = []
    for resolution in sorted(oof["resolution_minutes"].unique(), reverse=True):
        subset = oof.loc[oof["resolution_minutes"].eq(resolution)]
        for model_name in ["benchmark", "m0", "m1"]:
            probability_column = f"{model_name}_probability"
            for bin_number in range(bin_count):
                lower = bin_number / bin_count
                upper = (bin_number + 1) / bin_count
                if bin_number == bin_count - 1:
                    mask = subset[probability_column].ge(lower) & subset[
                        probability_column
                    ].le(upper)
                else:
                    mask = subset[probability_column].ge(lower) & subset[
                        probability_column
                    ].lt(upper)
                cell = subset.loc[mask]
                rows.append(
                    {
                        "resolution_minutes": int(resolution),
                        "model": model_name,
                        "probability_bin": bin_number + 1,
                        "bin_lower": lower,
                        "bin_upper": upper,
                        "event_count": int(len(cell)),
                        "mean_predicted_probability": (
                            float(cell[probability_column].mean()) if len(cell) else None
                        ),
                        "observed_agreement_rate": (
                            float(cell["next_bar_agreement_label"].mean())
                            if len(cell)
                            else None
                        ),
                    }
                )
    return pd.DataFrame(rows)


def expected_calibration_error(oof: pd.DataFrame, probability_column: str) -> float:
    """Calculate ten-bin fixed-width expected calibration error."""
    total = len(oof)
    error = 0.0
    for bin_number in range(10):
        lower = bin_number / 10
        upper = (bin_number + 1) / 10
        if bin_number == 9:
            mask = oof[probability_column].ge(lower) & oof[probability_column].le(upper)
        else:
            mask = oof[probability_column].ge(lower) & oof[probability_column].lt(upper)
        cell = oof.loc[mask]
        if len(cell):
            gap = abs(
                float(cell["next_bar_agreement_label"].mean())
                - float(cell[probability_column].mean())
            )
            error += len(cell) / total * gap
    return error


def _percentile(sorted_values: list[float], probability: float) -> float:
    position = probability * (len(sorted_values) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def paired_session_interval(
    sessions: list[str],
    differences: list[float],
    *,
    replications: int,
    confidence_level: float,
    seed: int,
) -> tuple[float, float]:
    """Bootstrap paired loss differences by complete validation session."""
    values = pd.DataFrame({"session": sessions, "difference": differences})
    grouped = values.groupby("session")["difference"].agg(["sum", "count"])
    clusters = [(float(row["sum"]), int(row["count"])) for _, row in grouped.iterrows()]
    rng = random.Random(seed)
    estimates: list[float] = []
    for _ in range(replications):
        selected = rng.choices(clusters, k=len(clusters))
        estimates.append(
            sum(total for total, _ in selected) / sum(count for _, count in selected)
        )
    estimates.sort()
    tail = (1.0 - confidence_level) / 2.0
    return _percentile(estimates, tail), _percentile(estimates, 1.0 - tail)


def summarize_resolution(
    oof: pd.DataFrame,
    *,
    replications: int,
    confidence_level: float,
    seed: int,
    maximum_ece_deterioration: float,
) -> dict[str, Any]:
    """Summarize OOF loss, calibration, and paired M1-minus-M0 uncertainty."""
    targets = oof["next_bar_agreement_label"].astype(int).tolist()
    metrics: dict[str, dict[str, float]] = {}
    for model_name in ["benchmark", "m0", "m1"]:
        probabilities = oof[f"{model_name}_probability"].astype(float).tolist()
        metrics[model_name] = {
            "brier_score": float(brier_score_loss(targets, probabilities)),
            "log_loss": float(log_loss(targets, probabilities, labels=[0, 1])),
            "expected_calibration_error": expected_calibration_error(
                oof, f"{model_name}_probability"
            ),
        }
    m0_probabilities = oof["m0_probability"].astype(float).tolist()
    m1_probabilities = oof["m1_probability"].astype(float).tolist()
    brier_differences = [
        m1 - m0
        for m1, m0 in zip(
            _brier_values(targets, m1_probabilities),
            _brier_values(targets, m0_probabilities),
            strict=True,
        )
    ]
    log_differences = [
        m1 - m0
        for m1, m0 in zip(
            _log_loss_values(targets, m1_probabilities),
            _log_loss_values(targets, m0_probabilities),
            strict=True,
        )
    ]
    sessions = oof["analysis_session_date"].astype(str).tolist()
    brier_interval = paired_session_interval(
        sessions,
        brier_differences,
        replications=replications,
        confidence_level=confidence_level,
        seed=seed,
    )
    log_interval = paired_session_interval(
        sessions,
        log_differences,
        replications=replications,
        confidence_level=confidence_level,
        seed=seed + 1,
    )
    brier_delta = sum(brier_differences) / len(brier_differences)
    log_delta = sum(log_differences) / len(log_differences)
    ece_delta = (
        metrics["m1"]["expected_calibration_error"]
        - metrics["m0"]["expected_calibration_error"]
    )
    evidence = (
        brier_interval[1] < 0
        and log_delta < 0
        and ece_delta <= maximum_ece_deterioration
    )
    return {
        "event_count": int(len(oof)),
        "session_count": int(oof["analysis_session_date"].nunique()),
        "session_start": str(oof["analysis_session_date"].min()),
        "session_end": str(oof["analysis_session_date"].max()),
        "observed_agreement_rate": float(oof["next_bar_agreement_label"].mean()),
        "metrics": metrics,
        "m1_minus_m0": {
            "brier_score_difference": brier_delta,
            "brier_session_block_95_ci": list(brier_interval),
            "log_loss_difference": log_delta,
            "log_loss_session_block_95_ci": list(log_interval),
            "expected_calibration_error_difference": ece_delta,
        },
        "incremental_magnitude_evidence": evidence,
    }


def weekday_metrics(oof: pd.DataFrame) -> pd.DataFrame:
    """Report M1-minus-M0 Brier stability across weekdays."""
    result = oof.copy()
    result["weekday"] = pd.to_datetime(result["analysis_session_date"]).dt.day_name()
    rows: list[dict[str, Any]] = []
    for resolution in sorted(result["resolution_minutes"].unique(), reverse=True):
        resolution_rows = result.loc[result["resolution_minutes"].eq(resolution)]
        for weekday in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
            subset = resolution_rows.loc[resolution_rows["weekday"].eq(weekday)]
            targets = subset["next_bar_agreement_label"].astype(int).tolist()
            m0 = subset["m0_probability"].astype(float).tolist()
            m1 = subset["m1_probability"].astype(float).tolist()
            rows.append(
                {
                    "resolution_minutes": int(resolution),
                    "weekday": weekday,
                    "event_count": int(len(subset)),
                    "session_count": int(subset["analysis_session_date"].nunique()),
                    "m0_brier_score": float(brier_score_loss(targets, m0)),
                    "m1_brier_score": float(brier_score_loss(targets, m1)),
                    "m1_minus_m0_brier": float(
                        brier_score_loss(targets, m1) - brier_score_loss(targets, m0)
                    ),
                }
            )
    return pd.DataFrame(rows)


def _write_csv(frame: pd.DataFrame, path: Path, *, index: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        frame.to_csv(
            stream,
            index=index,
            date_format="%Y-%m-%dT%H:%M:%SZ",
            float_format="%.12g",
            lineterminator="\n",
        )


def _write_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_trial_ledger(new_rows: pd.DataFrame, path: Path) -> None:
    if path.is_file():
        existing = pd.read_csv(path)
        run_ids = set(new_rows["run_id"].astype(str))
        existing = existing.loc[~existing["run_id"].astype(str).isin(run_ids)]
        combined = pd.concat([existing, new_rows], ignore_index=True)
    else:
        combined = new_rows
    if combined["trial_id"].duplicated().any():
        raise StateModelError("Trial ledger contains duplicate trial identifiers.")
    _write_csv(combined, path)


def build_state_model_artifacts(
    *,
    one_minute_outcomes: Path,
    five_minute_outcomes: Path,
    outcome_manifest_path: Path,
    config_path: Path,
    one_minute_oof_output: Path,
    five_minute_oof_output: Path,
    summary_output: Path,
    fold_metrics_output: Path,
    calibration_output: Path,
    coefficients_output: Path,
    weekday_output: Path,
    trial_ledger_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    """Run both registered resolutions and write auditable OOF artifacts."""
    config = _load_yaml(config_path)
    validate_state_model_config(config)
    outcome_manifest = json.loads(outcome_manifest_path.read_text(encoding="utf-8"))
    if outcome_manifest.get("status") != "development_only":
        raise StateModelError("Outcome manifest must remain development-only.")
    one_minute = load_model_population(
        one_minute_outcomes,
        str(outcome_manifest["one_minute_robustness"]["sha256"]),
    )
    five_minute = load_model_population(
        five_minute_outcomes,
        str(outcome_manifest["five_minute_primary"]["sha256"]),
    )
    implementation_hash = _hash_file(Path(__file__))
    run_key = "|".join(
        [
            _hash_file(config_path),
            _hash_file(outcome_manifest_path),
            implementation_hash,
        ]
    )
    run_id = hashlib.sha256(run_key.encode()).hexdigest()[:16]
    resolution_outputs: list[tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]] = []
    for resolution, frame in [(5, five_minute), (1, one_minute)]:
        resolution_outputs.append(
            run_resolution(
                frame,
                resolution_minutes=resolution,
                config=config,
                run_id=run_id,
            )
        )
    five_oof, five_folds, five_coefficients, five_trials = resolution_outputs[0]
    one_oof, one_folds, one_coefficients, one_trials = resolution_outputs[1]
    _write_csv(five_oof, five_minute_oof_output, index=True)
    _write_csv(one_oof, one_minute_oof_output, index=True)
    oof = pd.concat([five_oof, one_oof])
    fold_metrics = pd.concat([five_folds, one_folds], ignore_index=True)
    coefficients = pd.concat([five_coefficients, one_coefficients], ignore_index=True)
    trials = pd.concat([five_trials, one_trials], ignore_index=True)
    calibration = calibration_table(
        oof, int(config["evaluation"]["calibration_bins"])
    )
    weekday = weekday_metrics(oof)
    uncertainty = config["uncertainty"]
    evaluation = config["evaluation"]
    summary: dict[str, Any] = {
        "schema_version": 1,
        "model_version": config["model_version"],
        "status": "development_only",
        "run_id": run_id,
        "estimand": "next_bar_agreement_probability_given_current_agreement",
        "primary_comparison": "m1_minus_m0_brier_score",
        "five_minute_primary": summarize_resolution(
            five_oof,
            replications=int(uncertainty["replications"]),
            confidence_level=float(uncertainty["confidence_level"]),
            seed=int(uncertainty["seed"]) + 500,
            maximum_ece_deterioration=float(
                evaluation["maximum_ece_deterioration"]
            ),
        ),
        "one_minute_robustness": summarize_resolution(
            one_oof,
            replications=int(uncertainty["replications"]),
            confidence_level=float(uncertainty["confidence_level"]),
            seed=int(uncertainty["seed"]) + 100,
            maximum_ece_deterioration=float(
                evaluation["maximum_ece_deterioration"]
            ),
        ),
        "interpretation_rule": evaluation["evidence_rule"],
        "limitations": [
            "Development data have no pristine final holdout and were previously inspected.",
            "The model predicts state persistence, not returns or trading profitability.",
            "All preprocessing and regularization selection are nested inside past folds.",
            "A full analysis session is purged before every validation block.",
            "The one-minute result is robustness evidence and cannot replace the primary.",
        ],
    }
    _write_json(summary, summary_output)
    _write_csv(fold_metrics, fold_metrics_output)
    _write_csv(calibration, calibration_output)
    _write_csv(coefficients, coefficients_output)
    _write_csv(weekday, weekday_output)
    _write_trial_ledger(trials, trial_ledger_output)
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "model_version": config["model_version"],
        "status": "development_only",
        "generated_at": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "inputs": {
            "outcome_manifest_sha256": _hash_file(outcome_manifest_path),
            "config_sha256": _hash_file(config_path),
            "implementation_sha256": implementation_hash,
            "one_minute_outcomes_sha256": _hash_file(one_minute_outcomes),
            "five_minute_outcomes_sha256": _hash_file(five_minute_outcomes),
        },
        "local_oof_artifacts": {
            one_minute_oof_output.name: {
                "sha256": _hash_file(one_minute_oof_output),
                "committed": False,
            },
            five_minute_oof_output.name: {
                "sha256": _hash_file(five_minute_oof_output),
                "committed": False,
            },
        },
        "committed_artifacts": {
            path.name: {"sha256": _hash_file(path), "committed": True}
            for path in [
                summary_output,
                fold_metrics_output,
                calibration_output,
                coefficients_output,
                weekday_output,
                trial_ledger_output,
            ]
        },
        "limitations": outcome_manifest["limitations"],
    }
    _write_json(manifest, manifest_output)
    return summary


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--one-minute-outcomes", type=Path, required=True)
    parser.add_argument("--five-minute-outcomes", type=Path, required=True)
    parser.add_argument("--outcome-manifest", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--one-minute-oof-output", type=Path, required=True)
    parser.add_argument("--five-minute-oof-output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    parser.add_argument("--fold-metrics-output", type=Path, required=True)
    parser.add_argument("--calibration-output", type=Path, required=True)
    parser.add_argument("--coefficients-output", type=Path, required=True)
    parser.add_argument("--weekday-output", type=Path, required=True)
    parser.add_argument("--trial-ledger-output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    summary = build_state_model_artifacts(
        one_minute_outcomes=args.one_minute_outcomes,
        five_minute_outcomes=args.five_minute_outcomes,
        outcome_manifest_path=args.outcome_manifest,
        config_path=args.config,
        one_minute_oof_output=args.one_minute_oof_output,
        five_minute_oof_output=args.five_minute_oof_output,
        summary_output=args.summary_output,
        fold_metrics_output=args.fold_metrics_output,
        calibration_output=args.calibration_output,
        coefficients_output=args.coefficients_output,
        weekday_output=args.weekday_output,
        trial_ledger_output=args.trial_ledger_output,
        manifest_output=args.manifest,
    )
    primary = summary["five_minute_primary"]["m1_minus_m0"]
    print(
        "Completed purged walk-forward state comparison: "
        f"primary M1-M0 Brier={primary['brier_score_difference']:.8f}, "
        f"95% CI={primary['brier_session_block_95_ci']}."
    )


if __name__ == "__main__":
    main()
