"""Validation for the machine-readable research protocol."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


class ProtocolError(ValueError):
    """Raised when the research protocol violates its schema invariants."""


def load_protocol(path: Path) -> dict[str, Any]:
    """Load and validate a protocol YAML file."""
    with path.open(encoding="utf-8") as stream:
        payload = yaml.safe_load(stream)
    if not isinstance(payload, dict):
        raise ProtocolError("Protocol root must be a mapping.")
    validate_protocol(payload)
    return payload


def validate_protocol(protocol: dict[str, Any]) -> None:
    """Validate invariants needed before any research stage can run."""
    required_sections = {"research", "design", "data", "governance"}
    missing = required_sections.difference(protocol)
    if missing:
        raise ProtocolError(f"Missing protocol sections: {sorted(missing)}")

    if protocol.get("schema_version") != 1:
        raise ProtocolError("Unsupported schema_version; expected 1.")

    status = protocol.get("status")
    if status not in {"draft", "frozen"}:
        raise ProtocolError("status must be 'draft' or 'frozen'.")

    question = protocol["research"].get("primary_question", "")
    if not isinstance(question, str) or not question.strip():
        raise ProtocolError("A non-empty primary_question is required.")

    hypotheses = protocol["research"].get("hypotheses", [])
    if not hypotheses:
        raise ProtocolError("At least one hypothesis is required.")
    hypothesis_ids = [item.get("id") for item in hypotheses]
    if len(hypothesis_ids) != len(set(hypothesis_ids)):
        raise ProtocolError("Hypothesis IDs must be unique.")

    horizons = protocol["design"].get("candidate_horizons_minutes", [])
    if not horizons or any(not isinstance(value, int) or value <= 0 for value in horizons):
        raise ProtocolError("Candidate horizons must be positive integer minutes.")
    if horizons != sorted(set(horizons)):
        raise ProtocolError("Candidate horizons must be sorted and unique.")

    if protocol["design"].get("coherence_excludes_magnitude") is not True:
        raise ProtocolError(
            "Coherence must exclude joint intensity and magnitude balance."
        )
    if protocol["design"].get("primary_candle_component") != (
        "log_close_over_open_body"
    ):
        raise ProtocolError("The primary candle component must be the signed body return.")
    if protocol["design"].get("primary_uses_wicks_or_range") is not False:
        raise ProtocolError(
            "Wicks and high-low range must be excluded from the primary design."
        )

    frozen = bool(protocol["governance"].get("protocol_frozen"))
    if status == "frozen" and not frozen:
        raise ProtocolError("A frozen protocol must set governance.protocol_frozen=true.")
    if status == "frozen":
        unresolved = {
            "primary_horizon_minutes": protocol["design"].get("primary_horizon_minutes"),
            "final_holdout_start": protocol["data"].get("final_holdout_start"),
            "final_holdout_end": protocol["data"].get("final_holdout_end"),
        }
        missing_values = [name for name, value in unresolved.items() if value is None]
        if missing_values:
            raise ProtocolError(
                f"Frozen protocol has unresolved values: {sorted(missing_values)}"
            )


def main() -> None:
    """Validate a protocol from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to research protocol YAML")
    args = parser.parse_args()
    protocol = load_protocol(args.path)
    print(
        f"Valid {protocol['status']} protocol "
        f"v{protocol['protocol_version']} ({args.path})"
    )


if __name__ == "__main__":
    main()
