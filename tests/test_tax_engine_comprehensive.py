"""Acceptance Tests: Tax Engine comprehensive statutory rules, Section 393, Section 397(2), and Fail-Closed Guards."""
import pytest
from datetime import date
from src.tax.engine import TaxEngine, UnverifiedRateError


def test_section_393_dividend_tds_resident_individual():
    """
    Acceptance Test 7a: Section 393(1) Dividend TDS for Resident Individual.
    Threshold: ₹10,000 per company per Tax Year.
    Case 1: Dividend ₹8,000 <= ₹10,000 -> TDS = 0.
    Case 2: Dividend ₹15,000 > ₹10,000 -> TDS at 10% on entire amount = ₹1,500.
    """
    engine = TaxEngine()

    # Case 1: Below threshold
    res_below = engine.calculate_dividend_tds(
        gross_dividend=8000.0,
        payment_date=date(2026, 6, 15),
        is_individual=True,
        has_valid_pan=True
    )
    assert res_below["governing_section"] == "393(1)"
    assert res_below["tds_deducted"] == 0.0
    assert res_below["net_dividend_payable"] == 8000.0

    # Case 2: Above threshold -> Tax deducted on full gross dividend
    res_above = engine.calculate_dividend_tds(
        gross_dividend=15000.0,
        payment_date=date(2026, 6, 15),
        is_individual=True,
        has_valid_pan=True
    )
    assert res_above["governing_section"] == "393(1)"
    assert res_above["tds_deducted"] == 1500.0  # 15000 * 0.10
    assert res_above["net_dividend_payable"] == 13500.0


def test_section_393_dividend_tds_corporate_shareholder_nil_threshold():
    """
    Acceptance Test 7b: Section 393(1) Corporate Shareholder (Nil Threshold).
    For domestic company/firm/LLP, threshold is strictly Nil.
    Dividend of ₹4,000 must attract 10% TDS from Rupee 1.
    """
    engine = TaxEngine()
    res_corp = engine.calculate_dividend_tds(
        gross_dividend=4000.0,
        payment_date=date(2026, 6, 15),
        is_individual=False,  # Corporate recipient
        has_valid_pan=True
    )
    assert res_corp["threshold_applied"] == 0.0
    assert res_corp["tds_deducted"] == 400.0  # 4000 * 0.10
    assert res_corp["net_dividend_payable"] == 3600.0


def test_section_397_2_no_pan_penal_withholding():
    """
    Acceptance Test 7c: Section 397(2) Failure to furnish valid PAN.
    Requires penal deduction at 20% flat with zero threshold.
    """
    engine = TaxEngine()
    res_no_pan = engine.calculate_dividend_tds(
        gross_dividend=5000.0,
        payment_date=date(2026, 6, 15),
        is_individual=True,
        has_valid_pan=False  # Invalid or missing PAN
    )
    assert res_no_pan["governing_section"] == "397(2)"
    assert res_no_pan["tds_rate"] == 0.20
    assert res_no_pan["tds_deducted"] == 1000.0  # 5000 * 0.20
    assert res_no_pan["net_dividend_payable"] == 4000.0


def test_fail_closed_guard_for_unverified_rates():
    """
    Acceptance Test 8: Fail-closed behavior for unverified tax/turnover rates.
    If allow_unverified is False, invoking an unverified rate raises UnverifiedRateError.
    """
    # Create production engine (allow_unverified=False)
    engine_prod = TaxEngine(allow_unverified=False)
    
    # GST is verified, should succeed
    assert engine_prod.calculate_gst(brokerage=100.0) == 18.0

    # Test an unverified mock rate
    unverified_rule = [
        {"rate": 0.0000345, "effective_from": "2024-01-01", "verification_status": "unverified"}
    ]
    with pytest.raises(UnverifiedRateError, match="unverified"):
        engine_prod._find_rate_for_date(unverified_rule, date(2024, 6, 1))
