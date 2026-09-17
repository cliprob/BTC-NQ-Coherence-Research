"""Nested purged comparison of NQ-only and cross-market return forecasts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]
import yaml
from sklearn.linear_model import Ridge  # type: ignore[import-untyped]
from sklearn.metrics import (  # type: ignore[import-untyped]
    mean_absolute_error,
    mean_squared_error,
)
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

from btc_nq_coherence.state_models import (
    SessionFold,
    build_inner_folds,
    build_outer_folds,
    paired_session_interval,
)


class ReturnModelError(ValueError):
    """Raised when return-model evaluation violates the registered design."""


MOMENTUM_HORIZONS = (5, 15, 30, 60)
NQ_ONLY_FEATURES = (
    "nq_direction",
    "nq_magnitude",
    "nq_aligned_momentum_5m",
    "nq_aligned_momentum_15m",
    "nq_aligned_momentum_30m",
    "nq_aligned_momentum_60m",
    "session_sin_1",
    "session_cos_1",
    "session_sin_2",
    "session_cos_2",
    "weekday_tuesday",
    "weekday_wednesday",
    "weekday_thursday",
    "weekday_friday",
)
CROSS_MARKET_ADDITIONS = (
    "btc_magnitude",
    "btc_aligned_momentum_5m",
    "btc_aligned_momentum_15m",
    "btc_aligned_momentum_30m",
    "btc_aligned_momentum_60m",
    "coherence_15m",
    "coherence_30m",
    "coherence_60m",
    "joint_intensity",
    "magnitude_balance",
    "absolute_magnitude_balance",
)
CROSS_MARKET_FEATURES = (*NQ_ONLY_FEATURES, *CROSS_MARKET_ADDITIONS)
TARGET = "signed_nq_return_bps_5m"


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
        raise ReturnModelError(f"YAML root must be a mapping: {path}")
    return payload


def validate_return_model_config(config: dict[str, Any]) -> None:
    """Freeze target, baseline, nesting, folds, and inference before evaluation."""
    if config.get("schema_version") != 1 or config.get("status") != "development_only":
        raise ReturnModelError("Return-model config must remain schema 1 and development-only.")
    population = config.get("population", {})
    expected_population = {
        "feature_ready": True,
        "current_direction_agreement": 1,
        "primary_session_only": True,
        "required_within_session_history_minutes": 60,
        "target": TARGET,
        "target_winsorization": "none",
    }
    if population != expected_population:
        raise ReturnModelError("Return-model population or target has drifted.")
    derived = config.get("derived_features", {})
    if derived.get("momentum_horizons_minutes") != list(MOMENTUM_HORIZONS):
        raise ReturnModelError("Momentum horizons must remain 5/15/30/60 minutes.")
    if derived.get("cross_session_history") is not False:
        raise ReturnModelError("Return predictors cannot cross analysis sessions.")
    models = config.get("models", {})
    if models.get("nq_only", {}).get("predictors") != list(NQ_ONLY_FEATURES):
        raise ReturnModelError("NQ-only predictors differ from the registered baseline.")
    if models.get("cross_market", {}).get("additional_predictors") != list(
        CROSS_MARKET_ADDITIONS
    ):
        raise ReturnModelError("Cross-market additions differ from the protocol.")
    if models.get("preprocessing") != "standard_scaler_fit_on_training_fold_only":
        raise ReturnModelError("Preprocessing must be fitted inside each training fold.")
    if models.get("alpha_grid") != [0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]:
        raise ReturnModelError("Ridge alpha grid has drifted.")
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
        "inner_selection_aggregation": "event_weighted_oof_mean_squared_error",
        "partial_final_fold": "reject",
    }
    if walk != expected_walk:
        raise ReturnModelError("Walk-forward specification has drifted.")
    evaluation = config.get("evaluation", {})
    if evaluation.get("primary_metric") != "mean_squared_error":
        raise ReturnModelError("Mean squared error must remain the primary metric.")
    if evaluation.get("secondary_metric") != "mean_absolute_error":
        raise ReturnModelError("Mean absolute error must remain the secondary metric.")
    if evaluation.get("resolutions_minutes") != [5, 1]:
        raise ReturnModelError("Both five- and one-minute specifications are required.")
    uncertainty = config.get("uncertainty", {})
    if uncertainty.get("method") != "paired_analysis_session_block_bootstrap":
        raise ReturnModelError("Loss differences require paired session-block bootstrap.")
    if uncertainty.get("confidence_level") != 0.95:
        raise ReturnModelError("Confidence level must remain 95%.")
    if int(uncertainty.get("replications", 0)) < 1000:
        raise ReturnModelError("At least 1,000 bootstrap replications are required.")


def derive_return_features(frame: pd.DataFrame, bar_minutes: int) -> pd.DataFrame:
    """Create causal within-session momentum and calendar controls."""
    result = frame.copy().sort_index()
    expected_delta = pd.Timedelta(minutes=bar_minutes)
    for session_date, indexes in result.groupby(
        "analysis_session_date", sort=True
    ).groups.items():
        ordered = pd.DatetimeIndex(indexes).sort_values()
        if len(ordered) > 1 and not (ordered[1:] - ordered[:-1] == expected_delta).all():
            raise ReturnModelError(f"Non-consecutive bars in eligible session {session_date}.")
        session = result.loc[ordered]
        direction = session["nq_direction"]
        for horizon in MOMENTUM_HORIZONS:
            if horizon % bar_minutes:
                raise ReturnModelError("Momentum horizon is not divisible by bar interval.")
            periods = horizon // bar_minutes
            nq_momentum = (session["nq_close"] / session["nq_close"].shift(periods)).map(
                math.log, na_action="ignore"
            )
            btc_momentum = (
                session["btc_close"] / session["btc_close"].shift(periods)
            ).map(math.log, na_action="ignore")
            result.loc[ordered, f"nq_aligned_momentum_{horizon}m"] = (
                nq_momentum * direction
            )
            result.loc[ordered, f"btc_aligned_momentum_{horizon}m"] = (
                btc_momentum * direction
            )

    local = result.index.tz_convert("America/New_York")
    minutes_since_open = pd.Series(
        [(value.hour * 60 + value.minute) - (9 * 60 + 30) for value in local],
        index=result.index,
        dtype=float,
    )
    angle = minutes_since_open * (2.0 * math.pi / 390.0)
    result["session_sin_1"] = angle.map(math.sin)
    result["session_cos_1"] = angle.map(math.cos)
    result["session_sin_2"] = (angle * 2.0).map(math.sin)
    result["session_cos_2"] = (angle * 2.0).map(math.cos)
    weekdays = pd.to_datetime(result["analysis_session_date"]).dt.day_name()
    weekdays.index = result.index
    for weekday in ["Tuesday", "Wednesday", "Thursday", "Friday"]:
        result[f"weekday_{weekday.lower()}"] = weekdays.eq(weekday).astype(float)
    return result


def load_return_population(
    path: Path, expected_hash: str, *, bar_minutes: int
) -> pd.DataFrame:
    """Load registered outcomes and construct the fixed return-model population."""
    if not path.is_file() or _hash_file(path) != expected_hash:
        raise ReturnModelError(f"Outcome artifact identity mismatch: {path}")
    frame = pd.read_csv(path)
    required = {
        "timestamp_utc",
        "analysis_session_date",
        "bar_minutes",
        "feature_ready",
        "direction_agreement",
        "nq_open",
        "nq_close",
        "btc_close",
        "nq_direction",
        "nq_magnitude",
        "btc_magnitude",
        "coherence_15m",
        "coherence_30m",
        "coherence_60m",
        "joint_intensity",
        "magnitude_balance",
        "absolute_magnitude_balance",
        "outcome_ready_5m",
        TARGET,
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ReturnModelError(f"Outcome artifact is missing columns: {sorted(missing)}")
    frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True)
    frame = frame.set_index("timestamp_utc").sort_index()
    if frame.index.has_duplicates:
        raise ReturnModelError("Outcome timestamps must be unique.")
    if not frame["bar_minutes"].eq(bar_minutes).all():
        raise ReturnModelError("Outcome resolution does not match the requested interval.")
    frame = derive_return_features(frame, bar_minutes)
    ready = frame["feature_ready"].astype(str).str.lower().eq("true")
    outcome_ready = frame["outcome_ready_5m"].astype(str).str.lower().eq("true")
    mask = (
        ready
        & outcome_ready
        & frame["direction_agreement"].eq(1)
        & frame[TARGET].notna()
        & frame[list(CROSS_MARKET_FEATURES)].notna().all(axis=1)
    )
    columns = ["analysis_session_date", TARGET, *CROSS_MARKET_FEATURES]
    population = frame.loc[mask, columns].copy()
    if population.empty:
        raise ReturnModelError("No eligible return-model observations remain.")
    return population


def _rows_for_sessions(frame: pd.DataFrame, sessions: tuple[str, ...]) -> pd.DataFrame:
    return frame.loc[frame["analysis_session_date"].isin(sessions)]


def _new_pipeline(alpha: float) -> Pipeline:
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            ("model", Ridge(alpha=alpha, fit_intercept=True, solver="auto")),
        ]
    )


def fit_return_model(
    training: pd.DataFrame,
    validation: pd.DataFrame,
    *,
    features: tuple[str, ...],
    alpha: float,
) -> tuple[Pipeline, list[float]]:
    """Fit preprocessing and Ridge on past rows only."""
    pipeline = _new_pipeline(alpha)
    pipeline.fit(training[list(features)], training[TARGET])
    predictions = pipeline.predict(validation[list(features)])
    return pipeline, [float(value) for value in predictions]


def _squared_errors(targets: list[float], predictions: list[float]) -> list[float]:
    return [
        (target - prediction) ** 2
        for target, prediction in zip(targets, predictions, strict=True)
    ]


def _absolute_errors(targets: list[float], predictions: list[float]) -> list[float]:
    return [
        abs(target - prediction)
        for target, prediction in zip(targets, predictions, strict=True)
    ]


def tune_alpha(
    frame: pd.DataFrame,
    outer_fold: SessionFold,
    *,
    resolution_minutes: int,
    model_name: str,
    features: tuple[str, ...],
    alpha_grid: list[float],
    inner_fold_count: int,
    inner_validation_sessions: int,
    inner_purge_sessions: int,
    run_id: str,
) -> tuple[float, list[dict[str, Any]]]:
    """Select Ridge alpha using only nested, past-data OOF squared error."""
    inner_folds = build_inner_folds(
        outer_fold.train_sessions,
        fold_count=inner_fold_count,
        validation_sessions=inner_validation_sessions,
        purge_sessions=inner_purge_sessions,
    )
    scores: list[tuple[float, float, int, list[float]]] = []
    for alpha in alpha_grid:
        losses: list[float] = []
        fold_scores: list[float] = []
        for inner_fold in inner_folds:
            training = _rows_for_sessions(frame, inner_fold.train_sessions)
            validation = _rows_for_sessions(frame, inner_fold.validation_sessions)
            _, predictions = fit_return_model(
                training, validation, features=features, alpha=alpha
            )
            targets = validation[TARGET].astype(float).tolist()
            fold_losses = _squared_errors(targets, predictions)
            losses.extend(fold_losses)
            fold_scores.append(sum(fold_losses) / len(fold_losses))
        scores.append((sum(losses) / len(losses), alpha, len(losses), fold_scores))
    selected = min(scores, key=lambda item: (item[0], item[1]))[1]
    rows: list[dict[str, Any]] = []
    for mean_mse, alpha, event_count, fold_scores in scores:
        trial_key = f"{run_id}|{resolution_minutes}|{outer_fold.fold}|{model_name}|{alpha}"
        rows.append(
            {
                "trial_id": hashlib.sha256(trial_key.encode()).hexdigest()[:16],
                "run_id": run_id,
                "resolution_minutes": resolution_minutes,
                "outer_fold": outer_fold.fold,
                "model": model_name,
                "alpha": alpha,
                "inner_fold_count": len(inner_folds),
                "inner_event_count": event_count,
                "inner_oof_mean_squared_error": mean_mse,
                "inner_fold_mse_json": json.dumps(fold_scores),
                "selected": alpha == selected,
            }
        )
    return selected, rows


def _coefficient_rows(
    pipeline: Pipeline,
    features: tuple[str, ...],
    *,
    resolution_minutes: int,
    fold: int,
    model_name: str,
    alpha: float,
) -> list[dict[str, Any]]:
    estimator = pipeline.named_steps["model"]
    rows = [
        {
            "resolution_minutes": resolution_minutes,
            "fold": fold,
            "model": model_name,
            "alpha": alpha,
            "term": feature,
            "coefficient_bps_per_feature_sd": float(coefficient),
        }
        for feature, coefficient in zip(features, estimator.coef_, strict=True)
    ]
    rows.append(
        {
            "resolution_minutes": resolution_minutes,
            "fold": fold,
            "model": model_name,
            "alpha": alpha,
            "term": "intercept",
            "coefficient_bps_per_feature_sd": float(estimator.intercept_),
        }
    )
    return rows


def _metric_row(
    targets: list[float], predictions: list[float], model_name: str
) -> dict[str, float | str]:
    mse = float(mean_squared_error(targets, predictions))
    return {
        "model": model_name,
        "mean_squared_error": mse,
        "root_mean_squared_error_bps": math.sqrt(mse),
        "mean_absolute_error_bps": float(mean_absolute_error(targets, predictions)),
    }


def run_resolution(
    frame: pd.DataFrame,
    *,
    resolution_minutes: int,
    config: dict[str, Any],
    run_id: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Fit nested models and produce chronological OOF predictions."""
    sessions = sorted(str(value) for value in frame["analysis_session_date"].unique())
    walk = config["walk_forward"]
    folds = build_outer_folds(
        sessions,
        initial_training_sessions=int(walk["initial_training_sessions"]),
        validation_sessions=int(walk["validation_sessions"]),
        step_sessions=int(walk["step_sessions"]),
        purge_sessions=int(walk["purge_sessions"]),
    )
    alpha_grid = [float(value) for value in config["models"]["alpha_grid"]]
    oof_parts: list[pd.DataFrame] = []
    metric_rows: list[dict[str, Any]] = []
    coefficient_rows: list[dict[str, Any]] = []
    trial_rows: list[dict[str, Any]] = []
    model_features = [
        ("nq_only", NQ_ONLY_FEATURES),
        ("cross_market", CROSS_MARKET_FEATURES),
    ]
    for outer_fold in folds:
        training = _rows_for_sessions(frame, outer_fold.train_sessions)
        validation = _rows_for_sessions(frame, outer_fold.validation_sessions)
        predictions: dict[str, list[float]] = {
            "benchmark": [float(training[TARGET].mean())] * len(validation)
        }
        selected_alphas: dict[str, float] = {}
        for model_name, features in model_features:
            selected, trials = tune_alpha(
                frame,
                outer_fold,
                resolution_minutes=resolution_minutes,
                model_name=model_name,
                features=features,
                alpha_grid=alpha_grid,
                inner_fold_count=int(walk["inner_validation_folds"]),
                inner_validation_sessions=int(walk["inner_validation_sessions"]),
                inner_purge_sessions=int(walk["inner_purge_sessions"]),
                run_id=run_id,
            )
            selected_alphas[model_name] = selected
            trial_rows.extend(trials)
            pipeline, model_predictions = fit_return_model(
                training, validation, features=features, alpha=selected
            )
            predictions[model_name] = model_predictions
            coefficient_rows.extend(
                _coefficient_rows(
                    pipeline,
                    features,
                    resolution_minutes=resolution_minutes,
                    fold=outer_fold.fold,
                    model_name=model_name,
                    alpha=selected,
                )
            )
        targets = validation[TARGET].astype(float).tolist()
        for model_name, model_predictions in predictions.items():
            row: dict[str, Any] = dict(
                _metric_row(targets, model_predictions, model_name)
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
                    "selected_alpha": selected_alphas.get(model_name),
                }
            )
            metric_rows.append(row)
        oof = validation[["analysis_session_date", TARGET]].copy()
        oof["resolution_minutes"] = resolution_minutes
        oof["fold"] = outer_fold.fold
        for model_name, model_predictions in predictions.items():
            oof[f"{model_name}_prediction_bps"] = model_predictions
        oof_parts.append(oof)
    oof_frame = pd.concat(oof_parts).sort_index()
    if oof_frame.index.has_duplicates:
        raise ReturnModelError("Outer validation folds overlap.")
    return (
        oof_frame,
        pd.DataFrame(metric_rows),
        pd.DataFrame(coefficient_rows),
        pd.DataFrame(trial_rows),
    )


def summarize_resolution(
    oof: pd.DataFrame,
    *,
    replications: int,
    confidence_level: float,
    seed: int,
) -> dict[str, Any]:
    """Summarize OOF forecast loss and paired incremental uncertainty."""
    targets = oof[TARGET].astype(float).tolist()
    predictions = {
        model_name: oof[f"{model_name}_prediction_bps"].astype(float).tolist()
        for model_name in ["benchmark", "nq_only", "cross_market"]
    }
    metrics: dict[str, dict[str, float]] = {}
    benchmark_sse = sum(_squared_errors(targets, predictions["benchmark"]))
    for model_name, model_predictions in predictions.items():
        mse = float(mean_squared_error(targets, model_predictions))
        sse = sum(_squared_errors(targets, model_predictions))
        metrics[model_name] = {
            "mean_squared_error": mse,
            "root_mean_squared_error_bps": math.sqrt(mse),
            "mean_absolute_error_bps": float(
                mean_absolute_error(targets, model_predictions)
            ),
            "out_of_sample_r_squared_vs_benchmark": 1.0 - sse / benchmark_sse,
        }
    squared_differences = [
        cross - baseline
        for cross, baseline in zip(
            _squared_errors(targets, predictions["cross_market"]),
            _squared_errors(targets, predictions["nq_only"]),
            strict=True,
        )
    ]
    absolute_differences = [
        cross - baseline
        for cross, baseline in zip(
            _absolute_errors(targets, predictions["cross_market"]),
            _absolute_errors(targets, predictions["nq_only"]),
            strict=True,
        )
    ]
    sessions = oof["analysis_session_date"].astype(str).tolist()
    mse_interval = paired_session_interval(
        sessions,
        squared_differences,
        replications=replications,
        confidence_level=confidence_level,
        seed=seed,
    )
    mae_interval = paired_session_interval(
        sessions,
        absolute_differences,
        replications=replications,
        confidence_level=confidence_level,
        seed=seed + 1,
    )
    mse_difference = sum(squared_differences) / len(squared_differences)
    mae_difference = sum(absolute_differences) / len(absolute_differences)
    return {
        "event_count": int(len(oof)),
        "session_count": int(oof["analysis_session_date"].nunique()),
        "session_start": str(oof["analysis_session_date"].min()),
        "session_end": str(oof["analysis_session_date"].max()),
        "target_mean_bps": float(oof[TARGET].mean()),
        "target_standard_deviation_bps": float(oof[TARGET].std()),
        "metrics": metrics,
        "cross_market_minus_nq_only": {
            "mean_squared_error_difference": mse_difference,
            "squared_error_session_block_95_ci": list(mse_interval),
            "mean_absolute_error_difference_bps": mae_difference,
            "absolute_error_session_block_95_ci_bps": list(mae_interval),
        },
        "incremental_cross_market_return_evidence": (
            mse_interval[1] < 0 and mae_difference < 0
        ),
    }


def weekday_metrics(oof: pd.DataFrame) -> pd.DataFrame:
    """Expose incremental squared-error stability by weekday."""
    result = oof.copy()
    result["weekday"] = pd.to_datetime(result["analysis_session_date"]).dt.day_name()
    rows: list[dict[str, Any]] = []
    for resolution in sorted(result["resolution_minutes"].unique(), reverse=True):
        resolution_rows = result.loc[result["resolution_minutes"].eq(resolution)]
        for weekday in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
            subset = resolution_rows.loc[resolution_rows["weekday"].eq(weekday)]
            targets = subset[TARGET].astype(float).tolist()
            nq_only = subset["nq_only_prediction_bps"].astype(float).tolist()
            cross = subset["cross_market_prediction_bps"].astype(float).tolist()
            nq_mse = float(mean_squared_error(targets, nq_only))
            cross_mse = float(mean_squared_error(targets, cross))
            rows.append(
                {
                    "resolution_minutes": int(resolution),
                    "weekday": weekday,
                    "event_count": int(len(subset)),
                    "session_count": int(subset["analysis_session_date"].nunique()),
                    "nq_only_mean_squared_error": nq_mse,
                    "cross_market_mean_squared_error": cross_mse,
                    "cross_market_minus_nq_only_mse": cross_mse - nq_mse,
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
        raise ReturnModelError("Return-model trial ledger contains duplicate identifiers.")
    _write_csv(combined, path)


def build_return_model_artifacts(
    *,
    one_minute_outcomes: Path,
    five_minute_outcomes: Path,
    outcome_manifest_path: Path,
    config_path: Path,
    one_minute_oof_output: Path,
    five_minute_oof_output: Path,
    summary_output: Path,
    fold_metrics_output: Path,
    coefficients_output: Path,
    weekday_output: Path,
    trial_ledger_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    """Run the NQ-only versus cross-market return-forecast comparison."""
    config = _load_yaml(config_path)
    validate_return_model_config(config)
    outcome_manifest = json.loads(outcome_manifest_path.read_text(encoding="utf-8"))
    if outcome_manifest.get("status") != "development_only":
        raise ReturnModelError("Outcome manifest must remain development-only.")
    one_minute = load_return_population(
        one_minute_outcomes,
        str(outcome_manifest["one_minute_robustness"]["sha256"]),
        bar_minutes=1,
    )
    five_minute = load_return_population(
        five_minute_outcomes,
        str(outcome_manifest["five_minute_primary"]["sha256"]),
        bar_minutes=5,
    )
    implementation_hash = _hash_file(Path(__file__))
    run_key = "|".join(
        [_hash_file(config_path), _hash_file(outcome_manifest_path), implementation_hash]
    )
    run_id = hashlib.sha256(run_key.encode()).hexdigest()[:16]
    five_output = run_resolution(
        five_minute,
        resolution_minutes=5,
        config=config,
        run_id=run_id,
    )
    one_output = run_resolution(
        one_minute,
        resolution_minutes=1,
        config=config,
        run_id=run_id,
    )
    five_oof, five_folds, five_coefficients, five_trials = five_output
    one_oof, one_folds, one_coefficients, one_trials = one_output
    _write_csv(five_oof, five_minute_oof_output, index=True)
    _write_csv(one_oof, one_minute_oof_output, index=True)
    oof = pd.concat([five_oof, one_oof])
    fold_metrics = pd.concat([five_folds, one_folds], ignore_index=True)
    coefficients = pd.concat([five_coefficients, one_coefficients], ignore_index=True)
    trials = pd.concat([five_trials, one_trials], ignore_index=True)
    weekday = weekday_metrics(oof)
    uncertainty = config["uncertainty"]
    summary: dict[str, Any] = {
        "schema_version": 1,
        "model_version": config["model_version"],
        "status": "development_only",
        "run_id": run_id,
        "estimand": "signed_next_five_minute_nq_return_bps_given_current_agreement",
        "primary_comparison": "cross_market_minus_nq_only_mean_squared_error",
        "five_minute_primary": summarize_resolution(
            five_oof,
            replications=int(uncertainty["replications"]),
            confidence_level=float(uncertainty["confidence_level"]),
            seed=int(uncertainty["seed"]) + 5_000,
        ),
        "one_minute_robustness": summarize_resolution(
            one_oof,
            replications=int(uncertainty["replications"]),
            confidence_level=float(uncertainty["confidence_level"]),
            seed=int(uncertainty["seed"]) + 1_000,
        ),
        "interpretation_rule": config["evaluation"]["evidence_rule"],
        "limitations": [
            "Development data have no pristine final holdout and were previously inspected.",
            "The target is gross signed NQ response; no trade rule or cost model is applied.",
            "The first 60 cash-session minutes are feature warm-up and are not scored.",
            "Targets are not clipped or winsorized; MSE remains sensitive to tail returns.",
            "All preprocessing and alpha selection are nested inside past folds.",
        ],
    }
    _write_json(summary, summary_output)
    _write_csv(fold_metrics, fold_metrics_output)
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
    parser.add_argument("--coefficients-output", type=Path, required=True)
    parser.add_argument("--weekday-output", type=Path, required=True)
    parser.add_argument("--trial-ledger-output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    summary = build_return_model_artifacts(
        one_minute_outcomes=args.one_minute_outcomes,
        five_minute_outcomes=args.five_minute_outcomes,
        outcome_manifest_path=args.outcome_manifest,
        config_path=args.config,
        one_minute_oof_output=args.one_minute_oof_output,
        five_minute_oof_output=args.five_minute_oof_output,
        summary_output=args.summary_output,
        fold_metrics_output=args.fold_metrics_output,
        coefficients_output=args.coefficients_output,
        weekday_output=args.weekday_output,
        trial_ledger_output=args.trial_ledger_output,
        manifest_output=args.manifest,
    )
    primary = summary["five_minute_primary"]["cross_market_minus_nq_only"]
    print(
        "Completed purged return-forecast comparison: "
        f"primary cross-minus-NQ MSE={primary['mean_squared_error_difference']:.6f}, "
        f"95% CI={primary['squared_error_session_block_95_ci']}."
    )


if __name__ == "__main__":
    main()

