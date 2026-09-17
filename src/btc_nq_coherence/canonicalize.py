"""Build a synchronized development-only BTC–NQ minute dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]
import pandas_market_calendars as mcal  # type: ignore[import-untyped]
import yaml


class CanonicalizationError(ValueError):
    """Raised when canonicalization would violate the availability policy."""


@dataclass(frozen=True)
class ExcludedSession:
    """A calendar session rejected from an analysis role."""

    session_date: str
    role: str
    reasons: tuple[str, ...]
    missing_nq_minutes: int
    missing_btc_minutes: int


@dataclass(frozen=True)
class SessionSummary:
    """Eligibility summary for one analysis role."""

    candidate_sessions: int
    eligible_sessions: int
    eligible_minutes: int
    excluded_sessions: tuple[ExcludedSession, ...]
    eligible_sessions_by_weekday: dict[str, int]


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        payload = yaml.safe_load(stream)
    if not isinstance(payload, dict):
        raise CanonicalizationError(f"YAML root must be a mapping: {path}")
    return payload


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_identity(path: Path, expected: dict[str, Any], label: str) -> None:
    if not path.is_file():
        raise CanonicalizationError(f"Missing {label} file: {path}")
    if path.stat().st_size != expected.get("byte_size"):
        raise CanonicalizationError(f"{label} byte size differs from the registry.")
    if _hash_file(path) != expected.get("sha256"):
        raise CanonicalizationError(f"{label} SHA-256 differs from the registry.")


def load_nq(path: Path) -> pd.DataFrame:
    """Load the registered NQ schema to a unique UTC minute index."""
    frame = pd.read_csv(
        path,
        usecols=["date", "open", "high", "low", "close", "volume", "contract"],
    )
    timestamp = pd.to_datetime(
        frame.pop("date"), format="%Y%m%d %H:%M:%S", errors="raise"
    )
    frame.index = timestamp.dt.tz_localize(
        "America/Chicago", ambiguous="raise", nonexistent="raise"
    ).dt.tz_convert("UTC")
    frame.index.name = "timestamp_utc"
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise CanonicalizationError("NQ timestamps must be unique and increasing.")
    return frame.rename(columns={column: f"nq_{column}" for column in frame.columns})


def load_btc(path: Path) -> pd.DataFrame:
    """Load the registered Binance futures schema to a unique UTC minute index."""
    frame = pd.read_csv(
        path, usecols=["Open time", "Open", "High", "Low", "Close", "Volume"]
    )
    timestamp = pd.to_datetime(frame.pop("Open time"), utc=True, errors="raise")
    frame.index = timestamp
    frame.index.name = "timestamp_utc"
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise CanonicalizationError("BTC timestamps must be unique and increasing.")
    return frame.rename(columns={column: f"btc_{column.lower()}" for column in frame.columns})


def _roll_dates(nq: pd.DataFrame) -> set[str]:
    transitions = nq["nq_contract"].ne(nq["nq_contract"].shift())
    transition_index = nq.index[transitions][1:]
    return {
        timestamp.tz_convert("America/New_York").date().isoformat()
        for timestamp in transition_index
    }


def _evaluate_sessions(
    *,
    role: str,
    expected_by_session: list[tuple[str, pd.DatetimeIndex]],
    nq_index: pd.DatetimeIndex,
    btc_index: pd.DatetimeIndex,
    roll_dates: set[str],
) -> tuple[SessionSummary, dict[pd.Timestamp, str]]:
    excluded: list[ExcludedSession] = []
    eligible_timestamp_to_session: dict[pd.Timestamp, str] = {}
    weekday_counts: dict[str, int] = {}

    nq_timestamps = set(nq_index)
    btc_timestamps = set(btc_index)
    for session_date, expected in expected_by_session:
        missing_nq = sum(timestamp not in nq_timestamps for timestamp in expected)
        missing_btc = sum(timestamp not in btc_timestamps for timestamp in expected)
        reasons: list[str] = []
        if missing_nq:
            reasons.append("missing_nq_minutes")
        if missing_btc:
            reasons.append("missing_btc_minutes")
        if session_date in roll_dates:
            reasons.append("contract_transition_session")
        if reasons:
            excluded.append(
                ExcludedSession(
                    session_date=session_date,
                    role=role,
                    reasons=tuple(reasons),
                    missing_nq_minutes=missing_nq,
                    missing_btc_minutes=missing_btc,
                )
            )
            continue

        weekday = pd.Timestamp(session_date).day_name()
        weekday_counts[weekday] = weekday_counts.get(weekday, 0) + 1
        eligible_timestamp_to_session.update(
            {timestamp: session_date for timestamp in expected}
        )

    summary = SessionSummary(
        candidate_sessions=len(expected_by_session),
        eligible_sessions=len(expected_by_session) - len(excluded),
        eligible_minutes=len(eligible_timestamp_to_session),
        excluded_sessions=tuple(excluded),
        eligible_sessions_by_weekday=dict(sorted(weekday_counts.items())),
    )
    return summary, eligible_timestamp_to_session


def _primary_expected_sessions(
    start: pd.Timestamp, end: pd.Timestamp
) -> list[tuple[str, pd.DatetimeIndex]]:
    calendar = mcal.get_calendar("NYSE")
    schedule = calendar.schedule(start_date=start.date(), end_date=end.date())
    expected_sessions: list[tuple[str, pd.DatetimeIndex]] = []
    for session_label, _row in schedule.iterrows():
        expected = mcal.date_range(
            schedule.loc[[session_label]],
            frequency="1min",
            closed="left",
            force_close=False,
        )
        if expected.empty or expected[0] < start or expected[-1] > end:
            continue
        expected_sessions.append((session_label.date().isoformat(), expected))
    return expected_sessions


def _overnight_expected_sessions(
    start: pd.Timestamp, end: pd.Timestamp
) -> list[tuple[str, pd.DatetimeIndex]]:
    calendar = mcal.get_calendar("CME_Equity")
    schedule = calendar.schedule(start_date=start.date(), end_date=end.date())
    expected_sessions: list[tuple[str, pd.DatetimeIndex]] = []
    new_york = "America/New_York"
    for session_label, row in schedule.iterrows():
        market_open = row["market_open"]
        cash_open = pd.Timestamp(session_label.date(), tz=new_york) + pd.Timedelta(
            hours=9, minutes=30
        )
        cash_open = cash_open.tz_convert("UTC")
        if market_open >= cash_open or row["market_close"] < cash_open:
            continue
        expected = pd.date_range(
            start=market_open, end=cash_open, freq="1min", inclusive="left"
        )
        if expected.empty or expected[0] < start or expected[-1] > end:
            continue
        expected_sessions.append((session_label.date().isoformat(), expected))
    return expected_sessions


def canonicalize(
    *,
    registry_path: Path,
    study_path: Path,
    nq_path: Path,
    btc_path: Path,
    output_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    """Create synchronized rows and eligibility flags from the available files."""
    registry = _load_yaml(registry_path)
    study = _load_yaml(study_path)
    if study.get("status") != "development_only":
        raise CanonicalizationError("Available-data study must remain development-only.")
    availability = study.get("availability", {})
    if not isinstance(availability, dict) or availability.get(
        "confirmatory_claims_permitted"
    ) is not False:
        raise CanonicalizationError("Confirmatory claims must be disabled.")

    datasets = registry.get("datasets", {})
    source_ids = study.get("sources", {})
    if not isinstance(datasets, dict) or not isinstance(source_ids, dict):
        raise CanonicalizationError("Registry and source mappings are required.")
    nq_id = str(source_ids.get("nq_dataset_id"))
    btc_id = str(source_ids.get("btc_dataset_id"))
    nq_spec = datasets.get(nq_id)
    btc_spec = datasets.get(btc_id)
    if not isinstance(nq_spec, dict) or not isinstance(btc_spec, dict):
        raise CanonicalizationError("Selected datasets are absent from the registry.")
    nq_expected = nq_spec.get("expected")
    btc_expected = btc_spec.get("expected")
    if not isinstance(nq_expected, dict) or not isinstance(btc_expected, dict):
        raise CanonicalizationError("Selected datasets lack registered identities.")
    _validate_identity(nq_path, nq_expected, "NQ")
    _validate_identity(btc_path, btc_expected, "BTC")

    nq = load_nq(nq_path)
    btc = load_btc(btc_path)
    start = max(nq.index[0], btc.index[0])
    end = min(nq.index[-1], btc.index[-1])
    nq = nq.loc[start:end]
    btc = btc.loc[start:end]
    roll_dates = _roll_dates(nq)

    primary_summary, primary_map = _evaluate_sessions(
        role="primary",
        expected_by_session=_primary_expected_sessions(start, end),
        nq_index=nq.index,
        btc_index=btc.index,
        roll_dates=roll_dates,
    )
    overnight_summary, overnight_map = _evaluate_sessions(
        role="overnight_negative_control",
        expected_by_session=_overnight_expected_sessions(start, end),
        nq_index=nq.index,
        btc_index=btc.index,
        roll_dates=roll_dates,
    )

    canonical = nq.join(btc, how="inner")
    canonical.insert(0, "primary_session_date", canonical.index.map(primary_map))
    canonical.insert(1, "overnight_session_date", canonical.index.map(overnight_map))
    canonical.insert(2, "eligible_primary", canonical["primary_session_date"].notna())
    canonical.insert(
        3,
        "eligible_overnight_control",
        canonical["overnight_session_date"].notna(),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canonical.to_csv(output_path, index=True, date_format="%Y-%m-%dT%H:%M:%SZ")

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "status": "development_only",
        "generated_at": datetime.now(UTC).isoformat(),
        "calendar_library": f"pandas_market_calendars=={mcal.__version__}",
        "source_files": {
            "btc": {
                "dataset_id": btc_id,
                "sha256": btc_expected["sha256"],
                "row_count": int(len(btc)),
            },
            "nq": {
                "dataset_id": nq_id,
                "sha256": nq_expected["sha256"],
                "row_count": int(len(nq)),
            },
        },
        "common_range_utc": {
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        "roll_session_dates": sorted(roll_dates),
        "primary": asdict(primary_summary),
        "overnight_negative_control": asdict(overnight_summary),
        "canonical_output": {
            "file_name": output_path.name,
            "row_count": int(len(canonical)),
            "sha256": _hash_file(output_path),
            "committed": False,
        },
        "limitations": {
            "pre_etp_sample_available": False,
            "pristine_final_holdout_available": False,
            "confirmatory_claims_permitted": False,
        },
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--nq-path", type=Path, required=True)
    parser.add_argument("--btc-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    manifest = canonicalize(
        registry_path=args.registry,
        study_path=args.study,
        nq_path=args.nq_path,
        btc_path=args.btc_path,
        output_path=args.output,
        manifest_path=args.manifest,
    )
    print(
        "Canonicalized development data: "
        f"{manifest['canonical_output']['row_count']:,} synchronized minutes; "
        f"{manifest['primary']['eligible_sessions']:,} primary sessions; "
        f"{manifest['overnight_negative_control']['eligible_sessions']:,} "
        "overnight sessions."
    )


if __name__ == "__main__":
    main()
