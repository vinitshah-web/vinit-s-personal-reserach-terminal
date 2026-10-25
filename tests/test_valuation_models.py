"""Acceptance Tests: Exact Unrounded Valuation Models, Reverse DCF Solver & Bounds, and Banking DDM."""
import pytest
from src.core.valuation import ValuationEngine, ValuationModelError


def test_fcff_dcf_exact_unrounded_mathematical_fixture():
    """
    Acceptance Test 9: Damodaran FCFF numerical benchmark with exact unrounded floating-point calculations.
    Inputs:
    FCFF_0 = 60.0, 5-year growth = 8.0%, WACC = 12.0%, Terminal growth = 4.0%.
    Exact values:
    Year 1: 64.80 / 1.12 = 57.857143 Cr
    Year 2: 69.984 / 1.12^2 = 55.790816 Cr
    Year 3: 75.58272 / 1.12^3 = 53.798287 Cr
    Year 4: 81.629338 / 1.12^4 = 51.876920 Cr
    Year 5: 88.159685 / 1.12^5 = 50.024880 Cr
    Sum of discrete PV = 269.348046 Cr
    Terminal Value = (88.159685 * 1.04) / (0.12 - 0.04) = 1146.075900 Cr
    PV of Terminal Value = 1146.075900 / 1.12^5 = 650.314487 Cr
    Total Enterprise Value = 269.348046 + 650.314487 = 919.662533 Cr
    """
    engine = ValuationEngine()
    res = engine.calculate_fcff_dcf(
        fcff_0=60.0,
        growth_rates_5yr=[0.08] * 5,
        wacc=0.12,
        terminal_growth=0.04
    )

    # Assert exact unrounded floating point values to 4 decimal places
    assert round(res["sum_pv_discrete"], 4) == 269.3473
    assert round(res["terminal_value_year5"], 4) == 1146.0759
    assert round(res["pv_terminal_value"], 4) == 650.3142
    assert round(res["enterprise_value"], 4) == 919.6616


def test_reverse_dcf_solver_convergence_and_round_trip():
    """
    Acceptance Test 10a: Reverse DCF solver convergence.
    Solve for growth rate g* matching EV = 919.6625.
    Must converge back to g* = 8.00% (tolerance < 0.01%).
    """
    engine = ValuationEngine()
    implied_g = engine.solve_reverse_dcf(
        target_enterprise_value=919.6616,
        fcff_0=60.0,
        wacc=0.12,
        terminal_growth=0.04,
        lower_growth=-0.05,
        upper_growth=0.30
    )
    assert round(implied_g, 4) == 0.0800  # Exactly 8.00%


def test_valuation_engine_invalid_bounds_handling():
    """Acceptance Test 10b: Mathematical bounds and error handling."""
    engine = ValuationEngine()

    # 1. Terminal growth >= WACC
    with pytest.raises(ValuationModelError, match="cannot be greater than or equal to WACC"):
        engine.calculate_fcff_dcf(60.0, [0.08]*5, wacc=0.10, terminal_growth=0.10)

    # 2. Terminal growth > GDP cap (5.5%)
    with pytest.raises(ValuationModelError, match="exceeds long-term GDP growth cap"):
        engine.calculate_fcff_dcf(60.0, [0.08]*5, wacc=0.12, terminal_growth=0.06, terminal_gdp_cap=0.055)

    # 3. WACC <= 0
    with pytest.raises(ValuationModelError, match="WACC must be strictly positive"):
        engine.calculate_fcff_dcf(60.0, [0.08]*5, wacc=0.0, terminal_growth=0.04)

    # 4. Applying FCFF to financial institution
    with pytest.raises(ValuationModelError, match="cannot be applied to Banks"):
        engine.calculate_fcff_dcf(60.0, [0.08]*5, wacc=0.12, terminal_growth=0.04, is_financial=True)


def test_banking_ddm_with_sustainable_retention():
    """Verifies Banking DDM modeling regulatory capital retention b = g / ROE."""
    engine = ValuationEngine()
    # Net Income = 10,000 Cr, ROE = 15%, g = 5%, Cost of Equity = 12%
    # b = 5 / 15 = 33.33% retention. Payout = 66.67%.
    # D1 = 10000 * 1.05 * 0.6667 = 7000 Cr.
    # Fair Value = 7000 / (0.12 - 0.05) = 1,00,000 Cr.
    res = engine.calculate_banking_ddm(
        net_income_0=10000.0,
        return_on_equity=0.15,
        sustainable_growth=0.05,
        cost_of_equity=0.12
    )
    assert res["retention_ratio"] == 0.3333
    assert res["payout_ratio"] == 0.6667
    assert res["expected_dividend_1"] == 7000.0
    assert res["fair_equity_value"] == 100000.0


def test_enterprise_to_equity_value_bridge():
    """Verifies EV to Equity Value bridge and per-share derivation."""
    engine = ValuationEngine()
    bridge = engine.bridge_enterprise_to_equity_value(
        enterprise_value=10000.0,
        total_debt=2000.0,
        cash_and_equivalents=500.0,
        minority_interest=100.0,
        shares_outstanding=100.0  # 100 Cr shares
    )
    # Equity Value = 10000 - 2000 + 500 - 100 = 8400 Cr
    assert bridge["equity_value"] == 8400.0
    assert bridge["implied_per_share"] == 84.0  # 8400 / 100
