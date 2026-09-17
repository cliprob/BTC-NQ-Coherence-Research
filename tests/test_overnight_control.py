from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from btc_nq_coherence.overnight_control import (
    OvernightControlError,
    _runtime_config,
    validate_overnight_control_config,
)

ROOT = Path(__file__).resolve().parents[1]


def test_repository_overnight_control_config_is_frozen() -> None:
    config = yaml.safe_load((ROOT / "configs" / "overnight_control.yaml").read_text())
    validate_overnight_control_config(config)

    config["session"]["may_replace_primary"] = True
    with pytest.raises(OvernightControlError, match="session specification"):
        validate_overnight_control_config(config)


def test_runtime_override_changes_only_registered_walk_fields() -> None:
    primary = yaml.safe_load((ROOT / "configs" / "state_models.yaml").read_text())
    control = yaml.safe_load((ROOT / "configs" / "overnight_control.yaml").read_text())
    runtime = _runtime_config(primary, control)

    assert runtime["models"] == primary["models"]
    assert runtime["evaluation"] == primary["evaluation"]
    assert runtime["walk_forward"]["initial_training_sessions"] == 135
    assert primary["walk_forward"]["initial_training_sessions"] == 130


def test_committed_overnight_artifacts_match_manifest() -> None:
    manifest = json.loads(
        (ROOT / "data" / "registry" / "overnight_control_manifest.json").read_text()
    )

    for filename, metadata in manifest["committed_artifacts"].items():
        path = ROOT / "reports" / "development" / filename
        assert metadata["committed"] is True
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == metadata["sha256"]
