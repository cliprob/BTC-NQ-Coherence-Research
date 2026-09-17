"""Run the prespecified CME overnight negative-control analyses."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]
import yaml

from btc_nq_coherence.descriptive import (
    event_population,
    horizon_response,
    load_outcomes,
)
from btc_nq_coherence.return_models import (
    load_return_population,
    validate_return_model_config,
)
from btc_nq_coherence.return_models import (
    run_resolution as run_return_resolution,
)
from btc_nq_coherence.return_models import (
    summarize_resolution as summarize_return_resolution,
)
from btc_nq_coherence.return_models import (
    weekday_metrics as return_weekday_metrics,
)
from btc_nq_coherence.state_models import (
    calibration_table,
    load_model_population,
    validate_state_model_config,
)
from btc_nq_coherence.state_models import (
    run_resolution as run_state_resolution,
)
from btc_nq_coherence.state_models import (
    summarize_resolution as summarize_state_resolution,
)
from btc_nq_coherence.state_models import (
    weekday_metrics as state_weekday_metrics,
)


class OvernightControlError(ValueError):
    """Raised when the negative control differs from its registered specification."""


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
        raise OvernightControlError(f"YAML root must be a mapping: {path}")
    return payload


def validate_overnight_control_config(config: dict[str, Any]) -> None:
    """Freeze the control role, session, walk, and interpretation."""
    if config.get("schema_version") != 1:
        raise OvernightControlError("Overnight control schema must remain version 1.")
    if config.get("status") != "development_only_negative_control":
        raise OvernightControlError("Overnight control must remain development-only.")
    if config.get("role") != "overnight_negative_control":
        raise OvernightControlError("Analysis role has drifted.")
    expected_session = {
        "calendar": "CME_Equity",
        "timezone": "America/New_York",
        "start_previous_evening": "18:00",
        "end": "09:30",
        "expected_minutes": 930,
        "may_replace_primary": False,
    }
    if config.get("session") != expected_session:
        raise OvernightControlError("Overnight session specification has drifted.")
    expected_walk = {
        "session_order": "chronological",
        "expected_feature_ready_sessions": 488,
        "initial_training_sessions": 135,
        "validation_sessions": 22,
        "step_sessions": 22,
        "purge_sessions": 1,
        "expected_outer_folds": 16,
        "inner_validation_folds": 3,
        "inner_validation_sessions": 22,
        "inner_purge_sessions": 1,
        "partial_final_fold": "reject",
    }
    if config.get("walk_forward") != expected_walk:
        raise OvernightControlError("Overnight walk-forward specification has drifted.")
    state = config.get("state_model", {})
    if state.get("predictors_and_regularization") != "identical":
        raise OvernightControlError("State-model definitions must match primary.")
    if state.get("primary_metric") != "brier_score":
        raise OvernightControlError("State primary metric must remain Brier score.")
    returns = config.get("return_model", {})
    if returns.get("predictors_target_and_regularization") != "identical":
        raise OvernightControlError("Return-model definitions must match primary.")
    if returns.get("primary_metric") != "mean_squared_error":
        raise OvernightControlError("Return primary metric must remain MSE.")
    uncertainty = config.get("uncertainty", {})
    if uncertainty.get("method") != "paired_analysis_session_block_bootstrap":
        raise OvernightControlError("Uncertainty method has drifted.")
    if uncertainty.get("confidence_level") != 0.95:
        raise OvernightControlError("Confidence level must remain 95%.")
    if uncertainty.get("replications") != 5000:
        raise OvernightControlError("Bootstrap replication count must remain 5,000.")
    interpretation = config.get("interpretation", {})
    if interpretation.get("favorable_result_may_replace_primary") is not False:
        raise OvernightControlError("Control cannot replace the primary result.")
    if interpretation.get("unfavorable_result_may_be_omitted") is not False:
        raise OvernightControlError("Control must be reported regardless of result.")


def _runtime_config(primary: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(primary)
    control_walk = control["walk_forward"]
    result["walk_forward"].update(
        {
            "initial_training_sessions": control_walk["initial_training_sessions"],
            "validation_sessions": control_walk["validation_sessions"],
            "step_sessions": control_walk["step_sessions"],
            "purge_sessions": control_walk["purge_sessions"],
            "inner_validation_folds": control_walk["inner_validation_folds"],
            "inner_validation_sessions": control_walk["inner_validation_sessions"],
            "inner_purge_sessions": control_walk["inner_purge_sessions"],
            "partial_final_fold": control_walk["partial_final_fold"],
        }
    )
    return result


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
        raise OvernightControlError("Control trial ledger contains duplicate identifiers.")
    _write_csv(combined, path)


def _run_id(
    *,
    role: str,
    control_config_path: Path,
    primary_config_path: Path,
    outcome_manifest_path: Path,
    implementation_hash: str,
) -> str:
    key = "|".join(
        [
            role,
            _hash_file(control_config_path),
            _hash_file(primary_config_path),
            _hash_file(outcome_manifest_path),
            implementation_hash,
        ]
    )
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _descriptive_control(
    *,
    one_minute_outcomes: Path,
    five_minute_outcomes: Path,
    outcome_manifest: dict[str, Any],
    replications: int,
    confidence_level: float,
    seed: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    one = event_population(
        load_outcomes(
            one_minute_outcomes,
            str(outcome_manifest["one_minute_robustness"]["sha256"]),
        )
    )
    five = event_population(
        load_outcomes(
            five_minute_outcomes,
            str(outcome_manifest["five_minute_primary"]["sha256"]),
        )
    )
    responses = pd.concat(
        [
            horizon_response(
                five,
                resolution_minutes=5,
                horizons=[5, 15, 30, 60],
                replications=replications,
                confidence_level=confidence_level,
                seed=seed + 500,
            ),
            horizon_response(
                one,
                resolution_minutes=1,
                horizons=[1, 2, 3, 4, 5, 15, 30, 60],
                replications=replications,
                confidence_level=confidence_level,
                seed=seed + 100,
            ),
        ],
        ignore_index=True,
    )
    primary = responses.loc[
        responses["resolution_minutes"].eq(5)
        & responses["direction"].eq("all")
        & responses["horizon_minutes"].eq(5)
    ].iloc[0]
    one_minute_endpoint = responses.loc[
        responses["resolution_minutes"].eq(1)
        & responses["direction"].eq("all")
        & responses["horizon_minutes"].eq(5)
    ].iloc[0]
    summary = {
        "five_minute_primary": {
            "event_count": int(primary["event_count"]),
            "session_count": int(primary["session_count"]),
            "mean_signed_nq_return_bps": float(primary["mean_signed_nq_return_bps"]),
            "session_block_95_ci_bps": [
                float(primary["block_bootstrap_ci_lower_bps"]),
                float(primary["block_bootstrap_ci_upper_bps"]),
            ],
        },
        "one_minute_resolution_five_minute_endpoint": {
            "event_count": int(one_minute_endpoint["event_count"]),
            "session_count": int(one_minute_endpoint["session_count"]),
            "mean_signed_nq_return_bps": float(
                one_minute_endpoint["mean_signed_nq_return_bps"]
            ),
            "session_block_95_ci_bps": [
                float(one_minute_endpoint["block_bootstrap_ci_lower_bps"]),
                float(one_minute_endpoint["block_bootstrap_ci_upper_bps"]),
            ],
        },
    }
    return responses, summary


def build_overnight_control_artifacts(
    *,
    one_minute_outcomes: Path,
    five_minute_outcomes: Path,
    outcome_manifest_path: Path,
    control_config_path: Path,
    state_config_path: Path,
    return_config_path: Path,
    primary_state_summary_path: Path,
    primary_return_summary_path: Path,
    state_one_minute_oof_output: Path,
    state_five_minute_oof_output: Path,
    return_one_minute_oof_output: Path,
    return_five_minute_oof_output: Path,
    summary_output: Path,
    horizon_output: Path,
    state_fold_output: Path,
    state_calibration_output: Path,
    state_coefficients_output: Path,
    state_weekday_output: Path,
    state_trials_output: Path,
    return_fold_output: Path,
    return_coefficients_output: Path,
    return_weekday_output: Path,
    return_trials_output: Path,
    manifest_output: Path,
) -> dict[str, Any]:
    """Execute descriptive, state, and return overnight controls."""
    control = _load_yaml(control_config_path)
    state_config = _load_yaml(state_config_path)
    return_config = _load_yaml(return_config_path)
    validate_overnight_control_config(control)
    validate_state_model_config(state_config)
    validate_return_model_config(return_config)
    outcome_manifest = json.loads(outcome_manifest_path.read_text(encoding="utf-8"))
    if outcome_manifest.get("role") != "overnight_negative_control":
        raise OvernightControlError("Outcome manifest is not an overnight control artifact.")
    if outcome_manifest.get("status") != "development_only":
        raise OvernightControlError("Outcome manifest must remain development-only.")
    implementation_hash = _hash_file(Path(__file__))
    state_run_id = _run_id(
        role="overnight_state",
        control_config_path=control_config_path,
        primary_config_path=state_config_path,
        outcome_manifest_path=outcome_manifest_path,
        implementation_hash=implementation_hash,
    )
    return_run_id = _run_id(
        role="overnight_return",
        control_config_path=control_config_path,
        primary_config_path=return_config_path,
        outcome_manifest_path=outcome_manifest_path,
        implementation_hash=implementation_hash,
    )
    state_runtime = _runtime_config(state_config, control)
    return_runtime = _runtime_config(return_config, control)
    expected_sessions = int(control["walk_forward"]["expected_feature_ready_sessions"])

    state_one = load_model_population(
        one_minute_outcomes,
        str(outcome_manifest["one_minute_robustness"]["sha256"]),
    )
    state_five = load_model_population(
        five_minute_outcomes,
        str(outcome_manifest["five_minute_primary"]["sha256"]),
    )
    if state_one["analysis_session_date"].nunique() != expected_sessions:
        raise OvernightControlError("Unexpected one-minute feature-ready session count.")
    if state_five["analysis_session_date"].nunique() != expected_sessions:
        raise OvernightControlError("Unexpected five-minute feature-ready session count.")
    state_five_output = run_state_resolution(
        state_five,
        resolution_minutes=5,
        config=state_runtime,
        run_id=state_run_id,
    )
    state_one_output = run_state_resolution(
        state_one,
        resolution_minutes=1,
        config=state_runtime,
        run_id=state_run_id,
    )
    state_five_oof, state_five_folds, state_five_coef, state_five_trials = (
        state_five_output
    )
    state_one_oof, state_one_folds, state_one_coef, state_one_trials = state_one_output
    _write_csv(state_five_oof, state_five_minute_oof_output, index=True)
    _write_csv(state_one_oof, state_one_minute_oof_output, index=True)
    state_oof = pd.concat([state_five_oof, state_one_oof])
    state_folds = pd.concat([state_five_folds, state_one_folds], ignore_index=True)
    state_coefficients = pd.concat([state_five_coef, state_one_coef], ignore_index=True)
    state_trials = pd.concat([state_five_trials, state_one_trials], ignore_index=True)
    state_calibration = calibration_table(
        state_oof, int(state_config["evaluation"]["calibration_bins"])
    )
    state_weekday = state_weekday_metrics(state_oof)

    return_one = load_return_population(
        one_minute_outcomes,
        str(outcome_manifest["one_minute_robustness"]["sha256"]),
        bar_minutes=1,
    )
    return_five = load_return_population(
        five_minute_outcomes,
        str(outcome_manifest["five_minute_primary"]["sha256"]),
        bar_minutes=5,
    )
    if return_one["analysis_session_date"].nunique() != expected_sessions:
        raise OvernightControlError("Unexpected one-minute return session count.")
    if return_five["analysis_session_date"].nunique() != expected_sessions:
        raise OvernightControlError("Unexpected five-minute return session count.")
    return_five_output = run_return_resolution(
        return_five,
        resolution_minutes=5,
        config=return_runtime,
        run_id=return_run_id,
    )
    return_one_output = run_return_resolution(
        return_one,
        resolution_minutes=1,
        config=return_runtime,
        run_id=return_run_id,
    )
    return_five_oof, return_five_folds, return_five_coef, return_five_trials = (
        return_five_output
    )
    return_one_oof, return_one_folds, return_one_coef, return_one_trials = (
        return_one_output
    )
    _write_csv(return_five_oof, return_five_minute_oof_output, index=True)
    _write_csv(return_one_oof, return_one_minute_oof_output, index=True)
    return_oof = pd.concat([return_five_oof, return_one_oof])
    return_folds = pd.concat([return_five_folds, return_one_folds], ignore_index=True)
    return_coefficients = pd.concat(
        [return_five_coef, return_one_coef], ignore_index=True
    )
    return_trials = pd.concat([return_five_trials, return_one_trials], ignore_index=True)
    return_weekday = return_weekday_metrics(return_oof)

    uncertainty = control["uncertainty"]
    replications = int(uncertainty["replications"])
    confidence = float(uncertainty["confidence_level"])
    seed = int(uncertainty["seed"])
    horizon_table, descriptive_summary = _descriptive_control(
        one_minute_outcomes=one_minute_outcomes,
        five_minute_outcomes=five_minute_outcomes,
        outcome_manifest=outcome_manifest,
        replications=replications,
        confidence_level=confidence,
        seed=seed,
    )
    state_summary = {
        "five_minute_primary": summarize_state_resolution(
            state_five_oof,
            replications=replications,
            confidence_level=confidence,
            seed=seed + 55_000,
            maximum_ece_deterioration=float(
                state_config["evaluation"]["maximum_ece_deterioration"]
            ),
        ),
        "one_minute_robustness": summarize_state_resolution(
            state_one_oof,
            replications=replications,
            confidence_level=confidence,
            seed=seed + 11_000,
            maximum_ece_deterioration=float(
                state_config["evaluation"]["maximum_ece_deterioration"]
            ),
        ),
    }
    return_summary = {
        "five_minute_primary": summarize_return_resolution(
            return_five_oof,
            replications=replications,
            confidence_level=confidence,
            seed=seed + 50_000,
        ),
        "one_minute_robustness": summarize_return_resolution(
            return_one_oof,
            replications=replications,
            confidence_level=confidence,
            seed=seed + 10_000,
        ),
    }
    primary_state = json.loads(primary_state_summary_path.read_text(encoding="utf-8"))
    primary_return = json.loads(primary_return_summary_path.read_text(encoding="utf-8"))
    state_specificity = bool(
        primary_state["five_minute_primary"]["incremental_magnitude_evidence"]
        and not state_summary["five_minute_primary"]["incremental_magnitude_evidence"]
    )
    return_specificity = bool(
        primary_return["five_minute_primary"][
            "incremental_cross_market_return_evidence"
        ]
        and not return_summary["five_minute_primary"][
            "incremental_cross_market_return_evidence"
        ]
    )
    summary: dict[str, Any] = {
        "schema_version": 1,
        "control_version": control["control_version"],
        "status": "development_only_negative_control",
        "role": "overnight_negative_control",
        "session": control["session"],
        "descriptive_response": descriptive_summary,
        "state_model": state_summary,
        "return_model": return_summary,
        "specificity_assessment": {
            "cash_session_state_specificity_supported": state_specificity,
            "cash_session_return_specificity_supported": return_specificity,
            "state_rule": control["interpretation"]["state_specificity_rule"],
            "return_rule": control["interpretation"]["return_specificity_rule"],
        },
        "limitations": [
            "This is a required negative control and cannot select or replace primary results.",
            "Overnight and cash analyses use different eligible-session samples.",
            "The data are development-only and do not provide a pristine holdout.",
            "The stitched NQ source retains partial provenance limitations.",
        ],
    }
    _write_json(summary, summary_output)
    _write_csv(horizon_table, horizon_output)
    _write_csv(state_folds, state_fold_output)
    _write_csv(state_calibration, state_calibration_output)
    _write_csv(state_coefficients, state_coefficients_output)
    _write_csv(state_weekday, state_weekday_output)
    _write_trial_ledger(state_trials, state_trials_output)
    _write_csv(return_folds, return_fold_output)
    _write_csv(return_coefficients, return_coefficients_output)
    _write_csv(return_weekday, return_weekday_output)
    _write_trial_ledger(return_trials, return_trials_output)

    committed_paths = [
        summary_output,
        horizon_output,
        state_fold_output,
        state_calibration_output,
        state_coefficients_output,
        state_weekday_output,
        state_trials_output,
        return_fold_output,
        return_coefficients_output,
        return_weekday_output,
        return_trials_output,
    ]
    local_paths = [
        state_one_minute_oof_output,
        state_five_minute_oof_output,
        return_one_minute_oof_output,
        return_five_minute_oof_output,
    ]
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "control_version": control["control_version"],
        "status": "development_only_negative_control",
        "generated_at": datetime.now(UTC).isoformat(),
        "inputs": {
            "outcome_manifest_sha256": _hash_file(outcome_manifest_path),
            "control_config_sha256": _hash_file(control_config_path),
            "state_config_sha256": _hash_file(state_config_path),
            "return_config_sha256": _hash_file(return_config_path),
            "implementation_sha256": implementation_hash,
            "primary_state_summary_sha256": _hash_file(primary_state_summary_path),
            "primary_return_summary_sha256": _hash_file(primary_return_summary_path),
        },
        "local_oof_artifacts": {
            path.name: {"sha256": _hash_file(path), "committed": False}
            for path in local_paths
        },
        "committed_artifacts": {
            path.name: {"sha256": _hash_file(path), "committed": True}
            for path in committed_paths
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
    parser.add_argument("--control-config", type=Path, required=True)
    parser.add_argument("--state-config", type=Path, required=True)
    parser.add_argument("--return-config", type=Path, required=True)
    parser.add_argument("--primary-state-summary", type=Path, required=True)
    parser.add_argument("--primary-return-summary", type=Path, required=True)
    parser.add_argument("--state-one-minute-oof-output", type=Path, required=True)
    parser.add_argument("--state-five-minute-oof-output", type=Path, required=True)
    parser.add_argument("--return-one-minute-oof-output", type=Path, required=True)
    parser.add_argument("--return-five-minute-oof-output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    parser.add_argument("--horizon-output", type=Path, required=True)
    parser.add_argument("--state-fold-output", type=Path, required=True)
    parser.add_argument("--state-calibration-output", type=Path, required=True)
    parser.add_argument("--state-coefficients-output", type=Path, required=True)
    parser.add_argument("--state-weekday-output", type=Path, required=True)
    parser.add_argument("--state-trials-output", type=Path, required=True)
    parser.add_argument("--return-fold-output", type=Path, required=True)
    parser.add_argument("--return-coefficients-output", type=Path, required=True)
    parser.add_argument("--return-weekday-output", type=Path, required=True)
    parser.add_argument("--return-trials-output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    summary = build_overnight_control_artifacts(
        one_minute_outcomes=args.one_minute_outcomes,
        five_minute_outcomes=args.five_minute_outcomes,
        outcome_manifest_path=args.outcome_manifest,
        control_config_path=args.control_config,
        state_config_path=args.state_config,
        return_config_path=args.return_config,
        primary_state_summary_path=args.primary_state_summary,
        primary_return_summary_path=args.primary_return_summary,
        state_one_minute_oof_output=args.state_one_minute_oof_output,
        state_five_minute_oof_output=args.state_five_minute_oof_output,
        return_one_minute_oof_output=args.return_one_minute_oof_output,
        return_five_minute_oof_output=args.return_five_minute_oof_output,
        summary_output=args.summary_output,
        horizon_output=args.horizon_output,
        state_fold_output=args.state_fold_output,
        state_calibration_output=args.state_calibration_output,
        state_coefficients_output=args.state_coefficients_output,
        state_weekday_output=args.state_weekday_output,
        state_trials_output=args.state_trials_output,
        return_fold_output=args.return_fold_output,
        return_coefficients_output=args.return_coefficients_output,
        return_weekday_output=args.return_weekday_output,
        return_trials_output=args.return_trials_output,
        manifest_output=args.manifest,
    )
    state_delta = summary["state_model"]["five_minute_primary"]["m1_minus_m0"]
    return_delta = summary["return_model"]["five_minute_primary"][
        "cross_market_minus_nq_only"
    ]
    print(
        "Completed overnight negative control: "
        f"state Brier delta={state_delta['brier_score_difference']:.8f}; "
        f"return MSE delta={return_delta['mean_squared_error_difference']:.6f}."
    )


if __name__ == "__main__":
    main()

