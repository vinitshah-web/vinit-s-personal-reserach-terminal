"""Tests for Phase 3: Fundamental analysis engine, DuPont 5-factor, EV/EBITDA, and Banking metrics."""
from datetime import date

import pytest
from src.core.fundamentals.ratios import FundamentalAnalysisEngine
from src.ingestion.providers import apply_pb_display_rule


def pb_result(**overrides):
    inputs = {
        "price": 200.0,
        "price_date": date(2026, 10, 28),
        "total_equity_cr": 1_000.0,
        "shares_outstanding_cr": 100.0,
        "balance_sheet_date": date(2026, 3, 31),
    }
    inputs.update(overrides)
    return FundamentalAnalysisEngine().calculate_pb_ratio(**inputs)


def test_pb_ratio_calculates_from_complete_fresh_inputs():
    assert pb_result() == {"pb_ratio": 20.0, "pb_ratio_reason": None}


def test_pb_ratio_is_null_without_price():
    assert pb_result(price=None) == {
        "pb_ratio": None,
        "pb_ratio_reason": "Price is unavailable."
    }


def test_pb_ratio_is_null_without_price_date():
    assert pb_result(price_date=None) == {
        "pb_ratio": None,
        "pb_ratio_reason": "Price date is unavailable."
    }


def test_pb_ratio_is_null_without_total_equity():
    assert pb_result(total_equity_cr=None) == {
        "pb_ratio": None,
        "pb_ratio_reason": "Total equity is unavailable."
    }


def test_pb_ratio_is_null_without_shares_outstanding():
    assert pb_result(shares_outstanding_cr=None) == {
        "pb_ratio": None,
        "pb_ratio_reason": "Shares outstanding are unavailable."
    }


def test_pb_ratio_is_null_without_balance_sheet_date():
    assert pb_result(balance_sheet_date=None) == {
        "pb_ratio": None,
        "pb_ratio_reason": "Balance-sheet date is unavailable."
    }


def test_pb_ratio_is_null_for_balance_sheet_older_than_12_months():
    assert pb_result(balance_sheet_date=date(2025, 10, 27)) == {
        "pb_ratio": None,
        "pb_ratio_reason": "Balance sheet is more than 12 months older than the price date."
    }


def test_pb_ratio_accepts_balance_sheet_exactly_12_months_old():
    assert pb_result(balance_sheet_date=date(2025, 10, 28)) == {
        "pb_ratio": 20.0,
        "pb_ratio_reason": None
    }


@pytest.mark.parametrize(
    "symbol",
    [
        "BHARTIARTL", "BPCL", "DIXON", "ETERNAL", "FEDERALBNK",
        "ICICIBANK", "INFY", "IOC", "NAZARA", "PAYTM", "POLYCAB",
        "SBIN", "SWIGGY", "WIPRO"
    ]
)
def test_pb_display_rule_suppresses_unverifiable_cached_ratios(symbol):
    dossier = {"market_cap_cr": 100.0, "pe_ratio": 20.0, "pb_ratio": 3.0}

    result = apply_pb_display_rule(symbol, dossier)

    assert result["pb_ratio"] is None
    assert "12-month freshness rule" in result["pb_ratio_reason"]
    assert result["market_cap_cr"] == 100.0
    assert result["pe_ratio"] == 20.0


def test_dupont_5factor_numerical_fixture():
    """
    Verifies DuPont 5-Factor against the independent worked example:
    Net Income = 120, EBT = 160, EBIT = 200, Revenue = 1000, Total Assets = 2000, Equity = 800
    Tax Burden = 0.7500
    Interest Burden = 0.8000
    EBIT Margin = 0.2000
    Asset Turnover = 0.5000
    Equity Multiplier = 2.5000
    Product = 0.1500 (15.00% ROE)
    Direct ROE = 120 / 800 = 0.1500
    """
    engine = FundamentalAnalysisEngine()
    res = engine.calculate_dupont_5factor(
        net_income=120.0,
        ebt=160.0,
        ebit=200.0,
        revenue=1000.0,
        total_assets=2000.0,
        equity=800.0,
        is_financial=False
    )

    assert res["tax_burden"] == 0.7500
    assert res["interest_burden"] == 0.8000
    assert res["ebit_margin"] == 0.2000
    assert res["asset_turnover"] == 0.5000
    assert res["equity_multiplier"] == 2.5000
    assert res["roe_product"] == 0.1500
    assert res["roe_direct"] == 0.1500
    assert res["discrepancy"] == 0.0


def test_dupont_strictly_rejects_financial_institutions():
    """Anti-Mistake Guard: Never calculate standard DuPont ROE or EV/EBITDA for a Bank."""
    engine = FundamentalAnalysisEngine()
    with pytest.raises(ValueError, match="not applicable to financial institutions"):
        engine.calculate_dupont_5factor(
            net_income=1000.0,
            ebt=1200.0,
            ebit=1500.0,
            revenue=5000.0,
            total_assets=50000.0,
            equity=6000.0,
            is_financial=True
        )

    with pytest.raises(ValueError, match="cannot be calculated for Banks"):
        engine.calculate_ev_ebitda(
            market_cap=500000.0,
            total_debt=20000.0,
            cash_equivalents=5000.0,
            ebitda_ttm=40000.0,
            is_financial=True
        )


def test_banking_specific_metrics():
    """Verifies standard banking formulas (NIM, CASA, GNPA)."""
    engine = FundamentalAnalysisEngine()
    res = engine.calculate_banking_metrics(
        interest_earned=10000.0,
        interest_expended=6000.0,
        avg_earning_assets=100000.0,
        casa_deposits=45000.0,
        total_deposits=100000.0,
        gross_npa=2500.0,
        gross_advances=80000.0
    )

    assert res["net_interest_income"] == 4000.0
    assert res["net_interest_margin"] == 0.0400  # 4.00% NIM
    assert res["casa_ratio"] == 0.4500           # 45.0% CASA
    assert res["gnpa_ratio"] == round(2500.0 / 80000.0, 4)  # 3.125% -> 0.0312 in round-to-even
