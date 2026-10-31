"""Validation and atomicity checks for daily NSE EOD refreshes."""
from datetime import date
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.models import Base, MarketDataSync, PriceRaw, Security
from src.ingestion.daily_refresh import (
    SnapshotValidationError,
    export_additional_exchange_snapshot,
    fetch_exchange_snapshot,
    refresh_nse_snapshot,
)


REFRESH_DATE = date(2026, 10, 30)


class SnapshotAdapter:
    close = 326.0

    @classmethod
    def get_pipeline_status(cls):
        return {
            "trading_date": "2026-10-28",
            "stage": "derived",
            "prices_published_at": "2026-10-28T13:05:00Z",
        }

    @classmethod
    def get_snapshot(cls, trading_date):
        assert trading_date == date(2026, 10, 28)
        return [
            {
                "symbol": "ETERNAL",
                "series": "EQ",
                "isin": "INE758T01015",
                "name": "Eternal Limited",
                "open": 320.0,
                "high": 330.0,
                "low": 318.0,
                "close": cls.close,
                "last": cls.close,
                "prev_close": 319.0,
                "volume": 1_000_000,
                "turnover": 326_000_000.0,
                "trades": 50_000,
            }
        ]


@pytest.fixture
def refresh_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(
        Security(
            isin="INE758T01015",
            ticker_current="ETERNAL",
            company_name="Eternal Limited",
            listing_date=date(2010, 1, 1),
            series="EQ",
            is_financial=False,
        )
    )
    session.commit()
    yield session
    session.close()


def test_daily_refresh_inserts_verified_snapshot_idempotently(refresh_session):
    first = refresh_nse_snapshot(
        refresh_session, adapter=SnapshotAdapter, minimum_coverage=1,
        current_date=REFRESH_DATE,
    )
    second = refresh_nse_snapshot(
        refresh_session, adapter=SnapshotAdapter, minimum_coverage=1,
        current_date=REFRESH_DATE,
    )

    assert first.inserted_rows == 1
    assert first.updated_rows == 0
    assert second.inserted_rows == 0
    assert second.unchanged_rows == 1
    assert refresh_session.query(PriceRaw).count() == 1
    assert refresh_session.query(MarketDataSync).count() == 1
    assert refresh_session.query(PriceRaw).one().close_raw == 326.0


def test_daily_refresh_records_provider_correction(refresh_session):
    original_close = SnapshotAdapter.close
    try:
        refresh_nse_snapshot(
            refresh_session, adapter=SnapshotAdapter, minimum_coverage=1,
            current_date=REFRESH_DATE,
        )
        SnapshotAdapter.close = 327.0
        corrected = refresh_nse_snapshot(
            refresh_session, adapter=SnapshotAdapter, minimum_coverage=1,
            current_date=REFRESH_DATE,
        )
    finally:
        SnapshotAdapter.close = original_close

    assert corrected.updated_rows == 1
    assert refresh_session.query(PriceRaw).one().close_raw == 327.0
    assert refresh_session.query(MarketDataSync).count() == 2


def test_daily_refresh_rolls_back_invalid_ohlc(refresh_session):
    class InvalidAdapter(SnapshotAdapter):
        @classmethod
        def get_snapshot(cls, trading_date):
            rows = super().get_snapshot(trading_date)
            rows[0]["low"] = 400.0
            return rows

    with pytest.raises(SnapshotValidationError, match="OHLCV invariants"):
        refresh_nse_snapshot(
            refresh_session, adapter=InvalidAdapter, minimum_coverage=1,
            current_date=REFRESH_DATE,
        )

    assert refresh_session.query(PriceRaw).count() == 0
    assert refresh_session.query(MarketDataSync).count() == 0


def test_daily_refresh_rejects_partial_snapshot(refresh_session):
    with pytest.raises(SnapshotValidationError, match="coverage is too small"):
        refresh_nse_snapshot(
            refresh_session, adapter=SnapshotAdapter, minimum_coverage=2,
            current_date=REFRESH_DATE,
        )

    assert refresh_session.query(PriceRaw).count() == 0


def test_daily_refresh_rejects_stale_provider_status(refresh_session):
    with pytest.raises(SnapshotValidationError, match="pipeline is stale"):
        refresh_nse_snapshot(
            refresh_session,
            adapter=SnapshotAdapter,
            minimum_coverage=1,
            maximum_status_age_days=1,
            current_date=REFRESH_DATE,
        )

    assert refresh_session.query(PriceRaw).count() == 0


def test_bse_snapshot_accepts_empty_series_and_exports_composite_key(tmp_path):
    class BseAdapter(SnapshotAdapter):
        @classmethod
        def get_exchange_snapshot(cls, exchange, trading_date):
            assert exchange == "BSE"
            return [{
                "symbol": "500325",
                "series": "",
                "isin": "INE002A01018",
                "name": "Reliance Industries Ltd",
                "open": 1160.0,
                "high": 1175.0,
                "low": 1150.0,
                "close": 1164.9,
                "volume": 1000,
            }]

    result, rows = fetch_exchange_snapshot(
        BseAdapter,
        "BSE",
        minimum_coverage=1,
        current_date=REFRESH_DATE,
    )
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "latest_quotes.json").write_text("{}", encoding="utf-8")
    (data_dir / "market_data_status.json").write_text(
        json.dumps({"trading_date": "2026-10-28", "exchange": "NSE"}),
        encoding="utf-8",
    )
    search_path = data_dir / "securities_search_index.json"
    search_path.write_text(
        json.dumps([{"ticker": "RELIANCE", "exchange": "NSE"}]),
        encoding="utf-8",
    )

    export_additional_exchange_snapshot(result, rows, data_dir, search_path)

    quotes = json.loads((data_dir / "latest_quotes.json").read_text())
    search = json.loads(search_path.read_text())
    status = json.loads((data_dir / "market_data_status.json").read_text())
    assert quotes["BSE:500325"]["close"] == 1164.9
    assert any(row.get("exchange") == "BSE" for row in search)
    assert status["exchanges"]["BSE"]["status"] == "VERIFIED"
