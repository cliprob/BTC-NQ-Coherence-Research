from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_report_artifacts_match_integrity_manifest() -> None:
    manifest = json.loads(
        (ROOT / "report" / "report_manifest.json").read_text(encoding="utf-8")
    )
    pdf = ROOT / "output" / "pdf" / manifest["pdf"]["file_name"]

    assert manifest["status"] == "completed_development_report"
    assert manifest["page_count"] == 7
    assert pdf.is_file()
    assert _hash(pdf) == manifest["pdf"]["sha256"]
    assert _hash(ROOT / "configs" / "research_protocol.yaml") == manifest[
        "protocol_sha256"
    ]
    assert _hash(ROOT / "report" / "build_report.py") == manifest["builder_sha256"]

    for name, expected_hash in manifest["figures"].items():
        figure = ROOT / "report" / "figures" / name
        assert figure.is_file()
        assert _hash(figure) == expected_hash
