from pathlib import Path

import pytest

from btc_nq_coherence.protocol import ProtocolError, load_protocol, validate_protocol

ROOT = Path(__file__).resolve().parents[1]


def test_repository_protocol_is_valid_draft() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")

    assert protocol["status"] == "draft"
    assert protocol["governance"]["protocol_frozen"] is False
    assert protocol["design"]["strategy_stage_locked"] is True
    assert protocol["design"]["coherence_excludes_magnitude"] is True
    assert protocol["research"]["hypotheses"][1]["name"] == (
        "magnitude_conditioned_persistence"
    )


def test_frozen_protocol_rejects_unresolved_holdout() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    protocol["status"] = "frozen"
    protocol["governance"]["protocol_frozen"] = True

    with pytest.raises(ProtocolError, match="unresolved values"):
        validate_protocol(protocol)


def test_duplicate_hypothesis_ids_are_rejected() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    protocol["research"]["hypotheses"].append(
        {"id": "H1", "name": "duplicate", "role": "secondary"}
    )

    with pytest.raises(ProtocolError, match="must be unique"):
        validate_protocol(protocol)


def test_coherence_cannot_include_magnitude() -> None:
    protocol = load_protocol(ROOT / "configs" / "research_protocol.yaml")
    protocol["design"]["coherence_excludes_magnitude"] = False

    with pytest.raises(ProtocolError, match="Coherence must exclude"):
        validate_protocol(protocol)
