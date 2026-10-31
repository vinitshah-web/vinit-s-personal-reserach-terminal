"""Tests for truthful normalization of batch fundamentals."""
from datetime import datetime, timezone

from src.ingestion.fundamentals_snapshot import (
    derive_cross_listed_rows,
    normalize_yahoo_quote,
    yahoo_symbol,
)


def test_yahoo_symbol_routes_exchange_suffixes():
    assert yahoo_symbol("RELIANCE", "NSE") == "RELIANCE.NS"
    assert yahoo_symbol("500325", "BSE") == "500325.BO"


def test_normalized_fundamentals_keep_undated_pb_null():
    row = normalize_yahoo_quote(
        {
            "symbol": "RELIANCE.NS",
            "quoteType": "EQUITY",
            "currency": "INR",
            "longName": "Reliance Industries Limited",
            "marketCap": 16_000_000_000_000,
            "sharesOutstanding": 13_500_000_000,
            "trailingPE": 21.25,
            "priceToBook": 1.8,
            "bookValue": 650.0,
            "trailingAnnualDividendYield": 0.0045,
            "fiftyTwoWeekHigh": 1600.0,
            "fiftyTwoWeekLow": 1100.0,
        },
        {
            "exchange": "NSE",
            "ticker": "RELIANCE",
            "isin": "INE002A01018",
            "name": "RELIANCE INDUSTRIES LTD",
        },
        datetime(2026, 10, 31, tzinfo=timezone.utc),
    )

    assert row["market_cap_cr_provider"] == 1_600_000.0
    assert row["shares_outstanding_cr"] == 1350.0
    assert row["pe_ratio"] == 21.25
    assert row["dividend_yield_pct"] == 0.45
    assert row["pb_ratio"] is None
    assert "dated balance-sheet" in row["pb_ratio_reason"]
    assert row["business_summary"] is None
    assert row["source_class"] == "SECONDARY_AGGREGATOR"


def test_normalized_fundamentals_reject_wrong_currency():
    row = normalize_yahoo_quote(
        {"symbol": "ABC.NS", "quoteType": "EQUITY", "currency": "USD"},
        {"exchange": "NSE", "ticker": "ABC", "isin": "INE000A00000"},
    )
    assert row["data_status"] == "REJECTED"


def test_cross_listed_fundamentals_require_exact_isin_match():
    source = {
        "NSE:RELIANCE": {
            "key": "NSE:RELIANCE",
            "exchange": "NSE",
            "ticker": "RELIANCE",
            "isin": "INE002A01018",
            "company_name": "Reliance Industries Limited",
            "pe_ratio": 21.25,
            "data_status": "AVAILABLE",
        }
    }
    derived = derive_cross_listed_rows(source, [
        {"exchange": "BSE", "ticker": "RELIANCE", "isin": "INE002A01018", "name": "RELIANCE INDUSTRIES LTD."},
        {"exchange": "BSE", "ticker": "OTHER", "isin": "INE000A00000", "name": "Other"},
    ])

    assert derived["BSE:RELIANCE"]["pe_ratio"] == 21.25
    assert derived["BSE:RELIANCE"]["identity_basis"] == "Exact ISIN match to NSE:RELIANCE"
    assert "BSE:OTHER" not in derived
