"""Tests for Phase 0: Dual-Era Tax Engine rules, cutovers, and levies."""
import pytest
from datetime import date
from src.tax.engine import TaxEngine, UnverifiedRateError


def test_gst_calculation_base():
    """Verify GST is 18% strictly on service charges and excludes STT and Stamp Duty."""
    engine = TaxEngine()
    brokerage = 20.0
    exchange_charges = 0.76
    sebi_fees = 0.02
    dp_charges = 13.50

    # Base = 20 + 0.76 + 0.02 + 13.50 = 34.28
    # GST = 34.28 * 0.18 = 6.1704 -> 6.17
    gst = engine.calculate_gst(
        brokerage=brokerage,
        exchange_charges=exchange_charges,
        sebi_fees=sebi_fees,
        dp_charges=dp_charges
    )
    assert gst == 6.17


def test_tax_transition_it_act_1961_to_2025():
    """Verifies that sell dates before 2026-04-01 route to 1961 Act and on/after route to 2025 Act."""
    engine = TaxEngine()

    # Case 1: Sale in February 2026 (Legacy Act)
    res_legacy = engine.calculate_equity_capital_gains(
        buy_date=date(2025, 8, 1),
        buy_price=100.0,
        sell_date=date(2026, 2, 1),
        sell_price=120.0,
        quantity=100
    )
    assert res_legacy["era"] == "it_act_1961"
    assert res_legacy["governing_section"] == "111A"
    assert res_legacy["gain_type"] == "STCG"
    assert res_legacy["tax_rate"] == 0.20
    assert res_legacy["tax_payable"] == 400.0  # 2000 profit * 0.20

    # Case 2: Sale in May 2026 (Income-tax Act, 2025)
    res_modern = engine.calculate_equity_capital_gains(
        buy_date=date(2026, 1, 1),
        buy_price=100.0,
        sell_date=date(2026, 5, 1),
        sell_price=120.0,
        quantity=100
    )
    assert res_modern["era"] == "it_act_2025"
    assert res_modern["governing_section"] == "196"
    assert res_modern["gain_type"] == "STCG"
    assert res_modern["tax_rate"] == 0.20
    assert res_modern["tax_payable"] == 400.0


def test_ltcg_exemption_and_tax_rate():
    """Verifies LTCG taxation with annual exemption limit."""
    engine = TaxEngine()

    # Holding 400 days -> LTCG under IT Act 2025
    # Profit = (150 - 100) * 1000 = 50,000. Under 1.25L exemption -> tax = 0
    res_exempt = engine.calculate_equity_capital_gains(
        buy_date=date(2025, 4, 1),
        buy_price=100.0,
        sell_date=date(2026, 5, 6),
        sell_price=150.0,
        quantity=1000,
        cumulative_prior_ltcg_in_period=0.0
    )
    assert res_exempt["gain_type"] == "LTCG"
    assert res_exempt["governing_section"] == "198"
    assert res_exempt["tax_payable"] == 0.0

    # Profit = 2,00,000. Prior LTCG = 0. Exemption = 1,25,000. Taxable = 75,000 @ 12.5% = 9375
    res_taxable = engine.calculate_equity_capital_gains(
        buy_date=date(2025, 4, 1),
        buy_price=100.0,
        sell_date=date(2026, 5, 6),
        sell_price=300.0,
        quantity=1000,
        cumulative_prior_ltcg_in_period=0.0
    )
    assert res_taxable["taxable_gain"] == 75000.0
    assert res_taxable["tax_payable"] == 9375.0


def test_stt_and_stamp_duty_delivery():
    """Verifies STT (0.1% on buy & sell turnover) and Stamp Duty (0.015% on buy turnover)."""
    engine = TaxEngine()
    buy_turnover = 100000.0
    sell_turnover = 120000.0

    stt = engine.calculate_stt_delivery(buy_turnover, sell_turnover)
    assert stt["stt_buy"] == 100.0
    assert stt["stt_sell"] == 120.0
    assert stt["total_stt"] == 220.0

    stamp_duty = engine.calculate_stamp_duty_delivery(buy_turnover)
    assert stamp_duty == 15.0  # 100000 * 0.00015
