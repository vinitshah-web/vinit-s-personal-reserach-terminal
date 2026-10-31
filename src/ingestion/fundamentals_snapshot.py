"""Batch collection and normalization of non-authoritative company fundamentals.

Yahoo Finance is treated as a secondary aggregator. Values are published with
their retrieval time and are never described as exchange filings. Metrics that
need an unavailable accounting date, notably P/B, remain null.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any, Dict, Iterable, List, Mapping, Optional


def _finite_number(value: Any, *, positive: bool = False) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or (positive and number <= 0):
        return None
    return number


def yahoo_symbol(ticker: str, exchange: str) -> str:
    suffix = ".BO" if exchange.upper() == "BSE" else ".NS"
    return f"{ticker.strip().upper()}{suffix}"


def normalize_yahoo_quote(
    row: Mapping[str, Any],
    instrument: Mapping[str, Any],
    retrieved_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Normalize one provider row without filling absent facts."""
    retrieved = retrieved_at or datetime.now(timezone.utc)
    exchange = str(instrument.get("exchange") or "NSE").upper()
    ticker = str(instrument["ticker"]).upper()
    isin = instrument.get("isin")

    market_cap = _finite_number(row.get("marketCap"), positive=True)
    shares = _finite_number(row.get("sharesOutstanding"), positive=True)
    trailing_pe = _finite_number(row.get("trailingPE"), positive=True)
    forward_pe = _finite_number(row.get("forwardPE"), positive=True)
    trailing_eps = _finite_number(row.get("epsTrailingTwelveMonths"))
    book_value = _finite_number(row.get("bookValue"), positive=True)
    high_52w = _finite_number(row.get("fiftyTwoWeekHigh"), positive=True)
    low_52w = _finite_number(row.get("fiftyTwoWeekLow"), positive=True)
    dividend_yield_ratio = _finite_number(row.get("trailingAnnualDividendYield"))

    quote_type = str(row.get("quoteType") or "").upper()
    currency = str(row.get("currency") or "").upper()
    valid_equity = quote_type in {"EQUITY", ""}
    valid_currency = currency in {"INR", ""}

    return {
        "key": f"{exchange}:{ticker}",
        "exchange": exchange,
        "ticker": ticker,
        "provider_symbol": row.get("symbol") or yahoo_symbol(ticker, exchange),
        "isin": isin,
        "company_name": row.get("longName") or row.get("shortName") or instrument.get("name"),
        "business_summary": None,
        "business_summary_reason": "A verified company-description source was not available in the batch feed.",
        "sector": instrument.get("sector"),
        "industry": instrument.get("industry"),
        "market_cap_cr_provider": round(market_cap / 10_000_000, 2) if market_cap else None,
        "shares_outstanding_cr": round(shares / 10_000_000, 4) if shares else None,
        "pe_ratio": round(trailing_pe, 2) if trailing_pe else None,
        "pe_ratio_basis": "Provider-reported trailing P/E" if trailing_pe else None,
        "forward_pe_ratio": round(forward_pe, 2) if forward_pe else None,
        "trailing_eps": round(trailing_eps, 4) if trailing_eps is not None else None,
        "book_value_per_share": round(book_value, 4) if book_value else None,
        "pb_ratio": None,
        "pb_ratio_reason": "P/B unavailable because the batch source does not provide a dated balance-sheet equity value.",
        "dividend_yield_pct": (
            round(dividend_yield_ratio * 100, 4)
            if dividend_yield_ratio is not None and dividend_yield_ratio >= 0 else None
        ),
        "fifty_two_week_high": high_52w,
        "fifty_two_week_low": low_52w,
        "has_statements": False,
        "financial_statements": [],
        "source": "Yahoo Finance quote feed",
        "source_class": "SECONDARY_AGGREGATOR",
        "retrieved_at": retrieved.isoformat(),
        "data_status": "AVAILABLE" if valid_equity and valid_currency else "REJECTED",
        "data_status_reason": (
            None if valid_equity and valid_currency
            else f"Unexpected quote type or currency: {quote_type or 'missing'} / {currency or 'missing'}."
        ),
    }


def merge_fundamental_rows(
    existing: Mapping[str, Any], rows: Iterable[Mapping[str, Any]]
) -> Dict[str, Any]:
    merged = dict(existing)
    for row in rows:
        key = row.get("key")
        if key:
            merged[str(key)] = dict(row)
    return merged

