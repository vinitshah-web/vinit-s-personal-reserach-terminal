"""Tests for exchange-aware, fail-closed static quote selection."""
from src.api import main


def test_snapshot_quote_uses_exchange_key_and_verified_date(monkeypatch):
    monkeypatch.setattr(main, "LATEST_QUOTES", {
        "RELIANCE": {"isin": "INE002A01018", "trade_date": "2026-10-30", "close": 1165.0},
        "BSE:RELIANCE": {"isin": "INE002A01018", "trade_date": "2026-10-30", "close": 1164.9},
    })
    monkeypatch.setattr(main, "MARKET_DATA_STATUS", {"exchanges": {
        "NSE": {"status": "VERIFIED", "trading_date": "2026-10-30"},
        "BSE": {"status": "VERIFIED", "trading_date": "2026-10-30"},
    }})

    quote = main.get_snapshot_quote("BSE", "RELIANCE", "INE002A01018")

    assert quote["close"] == 1164.9
    assert quote["freshness"] == "LATEST_VERIFIED_EOD"


def test_snapshot_quote_rejects_stale_or_wrong_isin(monkeypatch):
    monkeypatch.setattr(main, "LATEST_QUOTES", {
        "BSE:ABC": {"isin": "INE111A00000", "trade_date": "2026-10-29", "close": 10.0},
    })
    monkeypatch.setattr(main, "MARKET_DATA_STATUS", {"exchanges": {
        "BSE": {"status": "VERIFIED", "trading_date": "2026-10-30"},
    }})

    assert main.get_snapshot_quote("BSE", "ABC", "INE111A00000") is None

    main.LATEST_QUOTES["BSE:ABC"]["trade_date"] = "2026-10-30"
    assert main.get_snapshot_quote("BSE", "ABC", "INE222A00000") is None
