from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from btc_nq_coherence.data_audit import DataAuditError, audit_csv


def _spec(path: Path) -> dict[str, object]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    row_count = len(path.read_text(encoding="utf-8").splitlines()) - 1
    return {
        "bar_interval_minutes": 1,
        "timestamp_column": "date",
        "timestamp_format": "%Y%m%d %H:%M:%S",
        "source_timezone": "America/Chicago",
        "columns": {
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
        },
        "contract_column": "contract",
        "price_increment": 0.25,
        "session_coverage": None,
        "expected": {
            "sha256": digest,
            "byte_size": path.stat().st_size,
            "row_count": row_count,
        },
    }


def test_audit_records_gap_and_contract_transition(tmp_path: Path) -> None:
    path = tmp_path / "nq.csv"
    path.write_text(
        "date,open,high,low,close,volume,contract\n"
        "20240307 08:30:00,18000.00,18000.50,17999.75,18000.25,10,202403\n"
        "20240307 08:31:00,18000.25,18001.00,18000.25,18000.75,12,202403\n"
        "20240307 08:33:00,18000.75,18001.25,18000.50,18001.00,8,202403\n"
        "20240307 08:34:00,18100.00,18100.50,18099.75,18100.25,15,202406\n",
        encoding="utf-8",
    )

    result = audit_csv("nq", _spec(path), path)

    assert result.expected_identity_matches is True
    assert result.structurally_valid is True
    assert result.non_one_minute_intervals == 1
    assert result.maximum_interval_minutes == 2
    assert len(result.contract_transitions) == 1
    assert result.contract_transitions[0].previous_contract == "202403"
    assert result.contract_transitions[0].next_contract == "202406"


def test_audit_rejects_off_tick_price_as_structurally_invalid(tmp_path: Path) -> None:
    path = tmp_path / "nq.csv"
    path.write_text(
        "date,open,high,low,close,volume,contract\n"
        "20240307 08:30:00,18000.10,18000.50,17999.75,18000.25,10,202403\n"
        "20240307 08:31:00,18000.25,18001.00,18000.25,18000.75,12,202403\n"
        "20240307 08:32:00,18000.75,18001.25,18000.50,18001.00,8,202403\n"
        "20240307 08:33:00,18001.00,18001.50,18000.75,18001.25,15,202403\n",
        encoding="utf-8",
    )

    result = audit_csv("nq", _spec(path), path)

    assert result.off_increment_price_values == 1
    assert result.structurally_valid is False


def test_audit_fails_on_missing_registered_column(tmp_path: Path) -> None:
    path = tmp_path / "nq.csv"
    path.write_text("date,open,high,low,close,volume\n", encoding="utf-8")

    with pytest.raises(DataAuditError, match="missing columns"):
        audit_csv("nq", _spec(path), path)


def test_calendar_audit_detects_missing_cash_session_minute(tmp_path: Path) -> None:
    path = tmp_path / "nq.csv"
    header = "date,open,high,low,close,volume,contract\n"
    rows = []
    for minute_offset in range(390):
        hour, minute = divmod(8 * 60 + 30 + minute_offset, 60)
        if hour == 10 and minute == 0:
            continue
        rows.append(
            f"20240307 {hour:02d}:{minute:02d}:00,"
            "18000.00,18000.50,17999.75,18000.25,10,202403\n"
        )
    path.write_text(header + "".join(rows), encoding="utf-8")
    spec = _spec(path)
    spec["session_coverage"] = {
        "protocol_calendar": "XNYS",
        "implementation_calendar": "NYSE",
    }

    result = audit_csv("nq", spec, path)

    assert result.primary_session_coverage is not None
    assert result.primary_session_coverage.complete_sessions_tested == 1
    assert result.primary_session_coverage.complete_sessions_with_all_minutes == 0
    assert result.primary_session_coverage.missing_minutes == 1
