"""Streaming structural audit for registered one-minute OHLCV files."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas_market_calendars as mcal  # type: ignore[import-untyped]
import yaml


class DataAuditError(ValueError):
    """Raised when a registry or dataset cannot be audited safely."""


@dataclass(frozen=True)
class ContractTransition:
    """A change in the contract identifier in timestamp order."""

    timestamp_utc: str
    previous_contract: str
    next_contract: str
    close_gap_bps: float


@dataclass(frozen=True)
class IncompleteSession:
    """Missing bars within one complete official cash session."""

    session_date: str
    expected_minutes: int
    observed_minutes: int
    missing_minutes: int


@dataclass(frozen=True)
class SessionCoverage:
    """Official-calendar coverage between complete file-edge sessions."""

    protocol_calendar: str
    implementation_calendar: str
    calendar_library: str
    complete_sessions_tested: int
    complete_sessions_with_all_minutes: int
    incomplete_sessions: tuple[IncompleteSession, ...]
    expected_minutes: int
    observed_minutes: int
    missing_minutes: int


@dataclass(frozen=True)
class AuditResult:
    """Serializable structural findings for one registered file."""

    dataset_id: str
    file_name: str
    sha256: str
    byte_size: int
    row_count: int
    first_timestamp_utc: str | None
    last_timestamp_utc: str | None
    duplicate_timestamps: int
    out_of_order_timestamps: int
    non_one_minute_intervals: int
    maximum_interval_minutes: float | None
    invalid_numeric_rows: int
    nonpositive_price_rows: int
    negative_volume_rows: int
    ohlc_invariant_violations: int
    off_increment_price_values: int
    missing_contract_rows: int
    contract_transitions: tuple[ContractTransition, ...]
    largest_same_contract_close_jump_bps: float
    primary_session_coverage: SessionCoverage | None
    expected_identity_matches: bool
    structurally_valid: bool

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible mapping."""
        return asdict(self)


def load_registry(path: Path) -> dict[str, Any]:
    """Load and minimally validate a data registry."""
    with path.open(encoding="utf-8") as stream:
        payload = yaml.safe_load(stream)
    if not isinstance(payload, dict):
        raise DataAuditError("Registry root must be a mapping.")
    if payload.get("schema_version") != 1:
        raise DataAuditError("Unsupported registry schema; expected version 1.")
    datasets = payload.get("datasets")
    if not isinstance(datasets, dict) or not datasets:
        raise DataAuditError("Registry must contain at least one dataset.")
    return payload


def sha256_file(path: Path) -> str:
    """Hash a file without loading it into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DataAuditError(f"{label} must be a mapping.")
    return value


def _parse_timestamp(value: str, timestamp_format: str, timezone_name: str) -> datetime:
    try:
        parsed = datetime.strptime(value, timestamp_format)
    except ValueError as error:
        raise DataAuditError(f"Invalid timestamp {value!r}: {error}") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(timezone_name))
    return parsed.astimezone(UTC)


def _parse_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite numeric value")
    return parsed


def _on_increment(value: float, increment: float) -> bool:
    units = value / increment
    return math.isclose(units, round(units), rel_tol=0.0, abs_tol=1e-7)


def _audit_session_coverage(
    observed_timestamps: set[datetime],
    first_timestamp: datetime | None,
    last_timestamp: datetime | None,
    settings: dict[str, Any] | None,
) -> SessionCoverage | None:
    if settings is None or first_timestamp is None or last_timestamp is None:
        return None
    protocol_calendar = str(settings.get("protocol_calendar", ""))
    implementation_calendar = str(settings.get("implementation_calendar", ""))
    if not protocol_calendar or not implementation_calendar:
        raise DataAuditError("Session coverage requires both calendar identifiers.")

    calendar = mcal.get_calendar(implementation_calendar)
    schedule = calendar.schedule(
        start_date=first_timestamp.date(), end_date=last_timestamp.date()
    )
    incomplete: list[IncompleteSession] = []
    sessions_tested = 0
    complete_sessions = 0
    expected_total = 0
    observed_total = 0

    for session_label, row in schedule.iterrows():
        market_open = row["market_open"].to_pydatetime()
        market_close = row["market_close"].to_pydatetime()
        last_expected_bar = market_close - timedelta(minutes=1)
        if market_open < first_timestamp or last_expected_bar > last_timestamp:
            continue

        one_session = schedule.loc[[session_label]]
        expected_index = mcal.date_range(
            one_session, frequency="1min", closed="left", force_close=False
        )
        expected = {timestamp.to_pydatetime() for timestamp in expected_index}
        observed_count = len(expected.intersection(observed_timestamps))
        expected_count = len(expected)
        missing_count = expected_count - observed_count
        sessions_tested += 1
        expected_total += expected_count
        observed_total += observed_count
        if missing_count == 0:
            complete_sessions += 1
        else:
            incomplete.append(
                IncompleteSession(
                    session_date=str(session_label.date()),
                    expected_minutes=expected_count,
                    observed_minutes=observed_count,
                    missing_minutes=missing_count,
                )
            )

    return SessionCoverage(
        protocol_calendar=protocol_calendar,
        implementation_calendar=implementation_calendar,
        calendar_library=f"pandas_market_calendars=={mcal.__version__}",
        complete_sessions_tested=sessions_tested,
        complete_sessions_with_all_minutes=complete_sessions,
        incomplete_sessions=tuple(incomplete),
        expected_minutes=expected_total,
        observed_minutes=observed_total,
        missing_minutes=expected_total - observed_total,
    )


def audit_csv(dataset_id: str, spec: dict[str, Any], path: Path) -> AuditResult:
    """Audit a registered CSV in one streaming pass plus a file hash pass."""
    if not path.is_file():
        raise DataAuditError(f"Dataset file does not exist: {path}")

    columns = _require_mapping(spec.get("columns"), f"{dataset_id}.columns")
    required_price_keys = ("open", "high", "low", "close")
    if any(key not in columns for key in (*required_price_keys, "volume")):
        raise DataAuditError(f"{dataset_id} must map OHLCV columns.")

    timestamp_column = str(spec.get("timestamp_column", ""))
    timestamp_format = str(spec.get("timestamp_format", ""))
    source_timezone = str(spec.get("source_timezone", ""))
    interval_minutes = int(spec.get("bar_interval_minutes", 0))
    if not timestamp_column or not timestamp_format or not source_timezone:
        raise DataAuditError(f"{dataset_id} has an incomplete timestamp specification.")
    if interval_minutes != 1:
        raise DataAuditError("This audit currently accepts registered one-minute bars only.")

    contract_column_value = spec.get("contract_column")
    contract_column = None if contract_column_value is None else str(contract_column_value)
    price_increment_value = spec.get("price_increment")
    price_increment = (
        None if price_increment_value is None else float(price_increment_value)
    )

    expected = _require_mapping(spec.get("expected"), f"{dataset_id}.expected")
    observed_hash = sha256_file(path)
    byte_size = path.stat().st_size

    row_count = 0
    first_timestamp: datetime | None = None
    last_timestamp: datetime | None = None
    duplicate_timestamps = 0
    out_of_order_timestamps = 0
    non_one_minute_intervals = 0
    maximum_interval_minutes: float | None = None
    invalid_numeric_rows = 0
    nonpositive_price_rows = 0
    negative_volume_rows = 0
    ohlc_invariant_violations = 0
    off_increment_price_values = 0
    missing_contract_rows = 0
    transitions: list[ContractTransition] = []
    largest_same_contract_jump = 0.0
    previous_timestamp: datetime | None = None
    previous_contract: str | None = None
    previous_close: float | None = None
    observed_timestamps: set[datetime] = set()

    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise DataAuditError(f"{dataset_id} has no CSV header.")
        required_headers = {
            timestamp_column,
            *(str(columns[key]) for key in (*required_price_keys, "volume")),
        }
        if contract_column is not None:
            required_headers.add(contract_column)
        missing_headers = required_headers.difference(reader.fieldnames)
        if missing_headers:
            raise DataAuditError(
                f"{dataset_id} is missing columns: {sorted(missing_headers)}"
            )

        for row in reader:
            row_count += 1
            timestamp = _parse_timestamp(
                row[timestamp_column], timestamp_format, source_timezone
            )
            observed_timestamps.add(timestamp)
            if first_timestamp is None:
                first_timestamp = timestamp
            if previous_timestamp is not None:
                delta_minutes = (timestamp - previous_timestamp).total_seconds() / 60.0
                if delta_minutes == 0:
                    duplicate_timestamps += 1
                elif delta_minutes < 0:
                    out_of_order_timestamps += 1
                if not math.isclose(delta_minutes, interval_minutes):
                    non_one_minute_intervals += 1
                if maximum_interval_minutes is None or delta_minutes > maximum_interval_minutes:
                    maximum_interval_minutes = delta_minutes

            try:
                open_price = _parse_float(row[str(columns["open"])])
                high_price = _parse_float(row[str(columns["high"])])
                low_price = _parse_float(row[str(columns["low"])])
                close_price = _parse_float(row[str(columns["close"])])
                volume = _parse_float(row[str(columns["volume"])])
            except (TypeError, ValueError):
                invalid_numeric_rows += 1
                previous_timestamp = timestamp
                last_timestamp = timestamp
                continue

            prices = (open_price, high_price, low_price, close_price)
            if any(value <= 0 for value in prices):
                nonpositive_price_rows += 1
            if volume < 0:
                negative_volume_rows += 1
            if high_price < max(open_price, close_price) or low_price > min(
                open_price, close_price
            ) or high_price < low_price:
                ohlc_invariant_violations += 1
            if price_increment is not None:
                off_increment_price_values += sum(
                    not _on_increment(value, price_increment) for value in prices
                )

            current_contract = None
            if contract_column is not None:
                current_contract = row[contract_column].strip()
                if not current_contract:
                    missing_contract_rows += 1
                    current_contract = None

            if previous_close is not None and previous_close > 0:
                close_jump_bps = (close_price / previous_close - 1.0) * 10_000.0
                if (
                    current_contract is not None
                    and previous_contract is not None
                    and current_contract != previous_contract
                ):
                    transitions.append(
                        ContractTransition(
                            timestamp_utc=timestamp.isoformat(),
                            previous_contract=previous_contract,
                            next_contract=current_contract,
                            close_gap_bps=round(close_jump_bps, 6),
                        )
                    )
                elif current_contract == previous_contract or contract_column is None:
                    largest_same_contract_jump = max(
                        largest_same_contract_jump, abs(close_jump_bps)
                    )

            previous_timestamp = timestamp
            previous_contract = current_contract
            previous_close = close_price
            last_timestamp = timestamp

    expected_row_count = expected.get("row_count")
    identity_matches = (
        observed_hash == expected.get("sha256")
        and byte_size == expected.get("byte_size")
        and (expected_row_count is None or row_count == expected_row_count)
    )
    structurally_valid = all(
        value == 0
        for value in (
            duplicate_timestamps,
            out_of_order_timestamps,
            invalid_numeric_rows,
            nonpositive_price_rows,
            negative_volume_rows,
            ohlc_invariant_violations,
            off_increment_price_values,
            missing_contract_rows,
        )
    )
    coverage_value = spec.get("session_coverage")
    coverage_settings = (
        None
        if coverage_value is None
        else _require_mapping(coverage_value, f"{dataset_id}.session_coverage")
    )
    session_coverage = _audit_session_coverage(
        observed_timestamps,
        first_timestamp,
        last_timestamp,
        coverage_settings,
    )

    return AuditResult(
        dataset_id=dataset_id,
        file_name=path.name,
        sha256=observed_hash,
        byte_size=byte_size,
        row_count=row_count,
        first_timestamp_utc=(
            None if first_timestamp is None else first_timestamp.isoformat()
        ),
        last_timestamp_utc=None if last_timestamp is None else last_timestamp.isoformat(),
        duplicate_timestamps=duplicate_timestamps,
        out_of_order_timestamps=out_of_order_timestamps,
        non_one_minute_intervals=non_one_minute_intervals,
        maximum_interval_minutes=maximum_interval_minutes,
        invalid_numeric_rows=invalid_numeric_rows,
        nonpositive_price_rows=nonpositive_price_rows,
        negative_volume_rows=negative_volume_rows,
        ohlc_invariant_violations=ohlc_invariant_violations,
        off_increment_price_values=off_increment_price_values,
        missing_contract_rows=missing_contract_rows,
        contract_transitions=tuple(transitions),
        largest_same_contract_close_jump_bps=round(largest_same_contract_jump, 6),
        primary_session_coverage=session_coverage,
        expected_identity_matches=identity_matches,
        structurally_valid=structurally_valid,
    )


def _parse_path_override(value: str) -> tuple[str, Path]:
    dataset_id, separator, raw_path = value.partition("=")
    if not separator or not dataset_id or not raw_path:
        raise argparse.ArgumentTypeError("Path overrides must use DATASET_ID=PATH.")
    return dataset_id, Path(raw_path).expanduser().resolve()


def main() -> None:
    """Audit one or more registered files and optionally write JSON findings."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument(
        "--path",
        action="append",
        type=_parse_path_override,
        required=True,
        metavar="DATASET_ID=PATH",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    registry = load_registry(args.registry)
    datasets = _require_mapping(registry["datasets"], "datasets")
    results: list[AuditResult] = []
    for dataset_id, path in args.path:
        if dataset_id not in datasets:
            raise DataAuditError(f"Unknown registered dataset: {dataset_id}")
        spec = _require_mapping(datasets[dataset_id], f"datasets.{dataset_id}")
        result = audit_csv(dataset_id, spec, path)
        results.append(result)
        print(
            f"{dataset_id}: {result.row_count:,} rows, "
            f"{result.first_timestamp_utc} -> {result.last_timestamp_utc}, "
            f"identity={'ok' if result.expected_identity_matches else 'mismatch'}, "
            f"structure={'ok' if result.structurally_valid else 'invalid'}"
        )

    payload = {
        "schema_version": 1,
        "registry_version": registry.get("registry_version"),
        "audited_at": datetime.now(UTC).isoformat(),
        "results": [result.to_dict() for result in results],
    }
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Wrote audit report: {args.output}")

    if any(
        not result.expected_identity_matches or not result.structurally_valid
        for result in results
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
