from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from btc_nq_coherence.descriptive import (
    DescriptiveError,
    event_population,
    feature_quantile_bins,
    response_surface,
    session_block_interval,
    validate_descriptive_config,
)

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _events() -> pd.DataFrame:
    rows = 50
    return pd.DataFrame(
        {
            "analysis_session_date": [
                f"2024-01-{index // 10 + 2:02d}" for index in range(rows)
            ],
            "feature_ready": True,
            "direction_agreement": 1,
            "common_direction": [1 if index % 2 == 0 else -1 for index in range(rows)],
            "joint_intensity": [float(index + 1) for index in range(rows)],
            "magnitude_balance": [index / rows - 0.5 for index in range(rows)],
            "signed_nq_return_bps_5m": [float(index % 7 - 3) for index in range(rows)],
            "nq_return_bps_5m": [float(index % 5 - 2) for index in range(rows)],
            "next_bar_agreement_label": [float(index % 2) for index in range(rows)],
            "persistence_run_minutes": [float(index % 4 * 5) for index in range(rows)],
            "persistence_end_observed": True,
        }
    )


def test_repository_descriptive_config_is_frozen() -> None:
    config = yaml.safe_load((ROOT / "configs" / "descriptive.yaml").read_text())
    validate_descriptive_config(config)

    config["response_surface"]["feature_bins"] = 10
    with pytest.raises(DescriptiveError, match="has drifted"):
        validate_descriptive_config(config)


def test_feature_bins_do_not_depend_on_outcomes() -> None:
    events = _events()
    original, original_edges = feature_quantile_bins(events, "joint_intensity", 5)
    events["signed_nq_return_bps_5m"] *= -1000
    changed, changed_edges = feature_quantile_bins(events, "joint_intensity", 5)

    pd.testing.assert_series_equal(original, changed)
    assert original_edges == changed_edges


def test_surface_keeps_all_cells_and_flags_small_counts() -> None:
    surface, edges = response_surface(_events(), bin_count=5, low_count_threshold=30)

    assert len(surface) == 75
    assert set(edges) == {"joint_intensity", "magnitude_balance"}
    assert surface["low_count"].all()


def test_session_block_interval_is_deterministic() -> None:
    events = _events()
    first = session_block_interval(
        events,
        "signed_nq_return_bps_5m",
        replications=1000,
        confidence_level=0.95,
        seed=7,
    )
    second = session_block_interval(
        events,
        "signed_nq_return_bps_5m",
        replications=1000,
        confidence_level=0.95,
        seed=7,
    )

    assert first == second


def test_event_population_excludes_unready_and_disagreement_rows() -> None:
    events = _events()
    events.loc[0, "feature_ready"] = False
    events.loc[1, "direction_agreement"] = -1

    assert len(event_population(events)) == len(events) - 2


def test_committed_aggregate_artifacts_match_manifest() -> None:
    manifest = json.loads(
        (ROOT / "data" / "registry" / "descriptive_manifest.json").read_text()
    )
    report_directory = ROOT / "reports" / "development"

    for file_name, metadata in manifest["artifacts"].items():
        assert metadata["committed"] is True
        assert _sha256(report_directory / file_name) == metadata["sha256"]
