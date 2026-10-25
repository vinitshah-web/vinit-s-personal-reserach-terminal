"""Acceptance tests for Phase 5: Valuation Lab Forward Models.
Verifies CAPM cost of equity, WACC capital weighting, and integrated valuation pipeline.
"""
import pytest
from src.core.valuation import ValuationEngine, ValuationModelError


def test_capm_cost_of_equity_calculation():
    # R_f = 6.82% (10Y Indian G-Sec), Beta = 1.15, ERP = 5.5%
    # K_e = 0.0682 + (1.15 * 0.055) = 0.0682 + 0.06325 = 0.13145 (13.145%)
    ke = ValuationEngine.calculate_capm_cost_of_equity(
        risk_free_rate=0.0682,
        beta=1.15,
        equity_risk_premium=0.055
    )
    assert abs(ke - 0.13145) < 1e-5

    # Negative risk-free rate or non-positive ERP rejected
    with pytest.raises(ValuationModelError):
        ValuationEngine.calculate_capm_cost_of_equity(risk_free_rate=-0.01, beta=1.0, equity_risk_premium=0.05)

    with pytest.raises(ValuationModelError):
        ValuationEngine.calculate_capm_cost_of_equity(risk_free_rate=0.07, beta=1.0, equity_risk_premium=0.0)


def test_wacc_capital_weighting_and_tax_shield():
    # K_e = 13.0%, K_d = 8.5%, Marginal Tax = 25.17% (Sec 115BAA corporate rate)
    # W_e = 80%, W_d = 20%
    # After-tax K_d = 0.085 * (1 - 0.2517) = 0.085 * 0.7483 = 0.0636055
    # WACC = (0.80 * 0.130) + (0.20 * 0.0636055) = 0.1040 + 0.0127211 = 0.1167211 (11.67%)
    wacc = ValuationEngine.calculate_wacc(
        cost_of_equity=0.130,
        cost_of_debt=0.085,
        marginal_tax_rate=0.2517,
        weight_equity=0.80,
        weight_debt=0.20
    )
    assert abs(wacc - 0.116721) < 1e-4

    # Weights not summing to 1.0 rejected
    with pytest.raises(ValuationModelError):
        ValuationEngine.calculate_wacc(0.12, 0.08, 0.25, 0.70, 0.20)


def test_integrated_dcf_and_per_share_bridge():
    """
    Tests end-to-end DCF to equity per-share calculation.
    FCFF0 = 100 Cr, 5yr growth 10%, WACC = 12%, g_term = 4.5%
    Debt = 200 Cr, Cash = 50 Cr, Shares = 10 Cr shares.
    """
    engine = ValuationEngine()
    dcf_res = engine.calculate_fcff_dcf(
        fcff_0=100.0,
        growth_rates_5yr=[0.10, 0.10, 0.10, 0.10, 0.10],
        wacc=0.12,
        terminal_growth=0.045
    )
    ev = dcf_res["enterprise_value"]
    assert ev > 1000.0

    bridge = engine.bridge_enterprise_to_equity_value(
        enterprise_value=ev,
        total_debt=200.0,
        cash_and_equivalents=50.0,
        minority_interest=10.0,
        shares_outstanding=10.0
    )

    expected_equity = ev - 200.0 + 50.0 - 10.0
    assert abs(bridge["equity_value"] - expected_equity) < 0.01
    assert bridge["implied_per_share"] == round(expected_equity / 10.0, 2)
