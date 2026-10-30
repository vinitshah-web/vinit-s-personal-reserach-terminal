"""Atomic daily ingestion of validated NSE end-of-day snapshots."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Optional, Type
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.db.models import MarketDataSync, PriceRaw, Security
from src.ingestion.providers import TejHQAdapter


ALLOWED_NSE_SERIES = {"EQ", "BE", "SM", "ST", "BZ"}
ISIN_PATTERN = re.compile(r"^[A-Z0-9]{12}$")
INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")


class SnapshotValidationError(RuntimeError):
    """Raised before commit when a market snapshot fails integrity checks."""


@dataclass(frozen=True)
class RefreshResult:
    provider: str
    exchange: str
    trading_date: str
    source_hash: str
    provider_published_at: Optional[str]
    fetched_at: str
    snapshot_rows: int
    validated_rows: int
    inserted_rows: int
    updated_rows: int
    unchanged_rows: int
    skipped_unknown_securities: int
    status: str = "VERIFIED"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _parse_provider_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _canonical_hash(rows: Iterable[Dict[str, Any]]) -> str:
    encoded = json.dumps(
        list(rows), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validated_snapshot_rows(
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    validated: List[Dict[str, Any]] = []
    seen_isins = set()

    for position, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise SnapshotValidationError(f"Snapshot row {position} is not an object.")

        series = str(row.get("series", "")).strip().upper()
        if series not in ALLOWED_NSE_SERIES:
            continue

        symbol = str(row.get("symbol", "")).strip().upper()
        isin = str(row.get("isin", "")).strip().upper()
        if not symbol or not ISIN_PATTERN.fullmatch(isin):
            raise SnapshotValidationError(
                f"Snapshot row {position} has an invalid symbol or ISIN."
            )
        if isin in seen_isins:
            raise SnapshotValidationError(f"Snapshot contains duplicate ISIN {isin}.")

        try:
            open_value = float(row["open"])
            high_value = float(row["high"])
            low_value = float(row["low"])
            close_value = float(row["close"])
            volume = int(row["volume"])
        except (KeyError, TypeError, ValueError) as exc:
            raise SnapshotValidationError(
                f"Snapshot row {position} has invalid OHLCV fields."
            ) from exc

        if (
            low_value <= 0
            or high_value < low_value
            or not low_value <= open_value <= high_value
            or not low_value <= close_value <= high_value
            or volume < 0
        ):
            raise SnapshotValidationError(
                f"Snapshot row {position} violates OHLCV invariants for {symbol}."
            )

        seen_isins.add(isin)
        validated.append(
            {
                "symbol": symbol,
                "series": series,
                "isin": isin,
                "name": str(row.get("name") or symbol).strip(),
                "open": open_value,
                "high": high_value,
                "low": low_value,
                "close": close_value,
                "volume": volume,
            }
        )

    return validated


def refresh_nse_snapshot(
    session: Session,
    adapter: Type[TejHQAdapter] = TejHQAdapter,
    minimum_coverage: int = 1_000,
    maximum_status_age_days: int = 7,
    current_date: Optional[date] = None,
) -> RefreshResult:
    """Validate and atomically persist the provider's latest full NSE snapshot."""
    status_payload = adapter.get_pipeline_status()
    trading_date = date.fromisoformat(status_payload["trading_date"])
    india_today = current_date or datetime.now(INDIA_TIMEZONE).date()
    age_days = (india_today - trading_date).days
    if age_days < 0:
        raise SnapshotValidationError("Provider trading date is in the future.")
    if age_days > maximum_status_age_days:
        raise SnapshotValidationError(
            f"Provider pipeline is stale: latest trading date is {trading_date.isoformat()}."
        )

    current_local_date = latest_local_market_date(session)
    if current_local_date and trading_date < current_local_date:
        raise SnapshotValidationError(
            "Provider trading date is older than the latest local market date "
            f"({current_local_date.isoformat()})."
        )

    snapshot_rows = adapter.get_snapshot(trading_date)
    source_hash = _canonical_hash(snapshot_rows)
    validated_rows = _validated_snapshot_rows(snapshot_rows)
    if len(validated_rows) < minimum_coverage:
        raise SnapshotValidationError(
            f"Snapshot coverage is too small: {len(validated_rows)} validated rows; "
            f"minimum is {minimum_coverage}."
        )

    known_securities = {
        security.isin: security
        for security in session.query(Security).filter(
            Security.isin.in_([row["isin"] for row in validated_rows])
        )
    }
    if len(known_securities) < minimum_coverage:
        raise SnapshotValidationError(
            f"Only {len(known_securities)} validated rows match the local security master; "
            f"minimum is {minimum_coverage}."
        )
    fetched_at = datetime.now(timezone.utc)
    source_file = f"tejhq_nse_snapshot_{trading_date.isoformat()}.json"
    inserted = updated = unchanged = skipped = 0

    try:
        for row in validated_rows:
            security = known_securities.get(row["isin"])
            if security is None:
                skipped += 1
                continue

            existing = session.get(
                PriceRaw, {"isin": row["isin"], "trade_date": trading_date}
            )
            values = (
                row["open"], row["high"], row["low"], row["close"], row["volume"]
            )
            if existing is None:
                session.add(
                    PriceRaw(
                        isin=row["isin"],
                        trade_date=trading_date,
                        open_raw=row["open"],
                        high_raw=row["high"],
                        low_raw=row["low"],
                        close_raw=row["close"],
                        volume_raw=row["volume"],
                        source_file=source_file,
                        file_hash=source_hash,
                        ingested_at=fetched_at,
                    )
                )
                inserted += 1
                continue

            current_values = (
                existing.open_raw,
                existing.high_raw,
                existing.low_raw,
                existing.close_raw,
                existing.volume_raw,
            )
            if current_values == values:
                unchanged += 1
                continue

            existing.open_raw = row["open"]
            existing.high_raw = row["high"]
            existing.low_raw = row["low"]
            existing.close_raw = row["close"]
            existing.volume_raw = row["volume"]
            existing.source_file = source_file
            existing.file_hash = source_hash
            existing.ingested_at = fetched_at
            updated += 1

        previous_sync = session.query(MarketDataSync).filter_by(
            provider="TejHQ", exchange="NSE", trading_date=trading_date,
            source_hash=source_hash
        ).first()
        provider_published_at = _parse_provider_timestamp(
            status_payload.get("prices_published_at")
        )
        if previous_sync is None:
            session.add(
                MarketDataSync(
                    provider="TejHQ",
                    exchange="NSE",
                    trading_date=trading_date,
                    provider_published_at=provider_published_at,
                    fetched_at=fetched_at,
                    row_count=len(validated_rows),
                    inserted_count=inserted,
                    updated_count=updated,
                    unchanged_count=unchanged,
                    skipped_count=skipped,
                    source_hash=source_hash,
                    status="VERIFIED",
                )
            )
        session.commit()
    except Exception:
        session.rollback()
        raise

    return RefreshResult(
        provider="TejHQ",
        exchange="NSE",
        trading_date=trading_date.isoformat(),
        source_hash=source_hash,
        provider_published_at=(
            provider_published_at.isoformat() if provider_published_at else None
        ),
        fetched_at=fetched_at.isoformat(),
        snapshot_rows=len(snapshot_rows),
        validated_rows=len(validated_rows),
        inserted_rows=inserted,
        updated_rows=updated,
        unchanged_rows=unchanged,
        skipped_unknown_securities=skipped,
    )


def latest_local_market_date(session: Session) -> Optional[date]:
    return session.query(func.max(PriceRaw.trade_date)).scalar()


def export_static_snapshot(
    result: RefreshResult,
    rows: Iterable[PriceRaw],
    securities: Dict[str, Security],
    output_directory: Path,
) -> None:
    """Atomically publish the compact snapshot consumed by GitHub Pages."""
    output_directory.mkdir(parents=True, exist_ok=True)
    quote_payload = {
        securities[row.isin].ticker_current: {
            "symbol": securities[row.isin].ticker_current,
            "isin": row.isin,
            "trade_date": row.trade_date.isoformat(),
            "open": row.open_raw,
            "high": row.high_raw,
            "low": row.low_raw,
            "close": row.close_raw,
            "volume": row.volume_raw,
            "source": "TejHQ / NSE EOD snapshot",
            "source_hash": row.file_hash,
        }
        for row in rows
        if row.isin in securities
    }
    for filename, payload in (
        ("latest_quotes.json", quote_payload),
        ("market_data_status.json", result.to_dict()),
    ):
        target = output_directory / filename
        temporary = target.with_suffix(f"{target.suffix}.tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        temporary.replace(target)
