"""Acceptance tests for Statutory Capital Loss Set-Off & Carry-Forward.
Verifies Section 70/74 (IT Act 1961) and Section 108/111 (IT Act 2025):
- STCL can set off against both STCG and LTCG
- LTCL can ONLY set off against LTCG (strictly prohibited against STCG)
- Annual ₹1.25L exemption applied only to net remaining LTCG
- Unabsorbed loss carry-forward tracking
"""
from datetime import date
import pytest
from src.tax.engine import TaxEngine


def test_stcl_sets_off_against_stcg_and_ltcg():
    """
    STCL = ₹50,000.
    STCG = ₹30,000.
    LTCG = ₹1,50,000.
    1. STCL sets off against STCG first: Net STCG = ₹0, Remaining STCL = ₹20,000.
    2. Remaining STCL sets off against LTCG: Net LTCG = ₹1,50,000 - ₹20,000 = ₹1,30,000.
    3. Exemption ₹1.25L applies to net LTCG: Taxable LTCG = ₹1,30,000 - ₹1,25,000 = ₹5,000.
    4. Tax @ 12.5% = ₹625.00.
    """
    engine = TaxEngine()
    trades = [
        {"buy_date": date(2025, 4, 1), "sell_date": date(2025, 6, 1), "buy_price": 100.0, "sell_price": 50.0, "quantity": 1000},  # STCL ₹50k
        {"buy_date": date(2025, 4, 1), "sell_date": date(2025, 7, 1), "buy_price": 100.0, "sell_price": 130.0, "quantity": 1000}, # STCG ₹30k
        {"buy_date": date(2024, 4, 1), "sell_date": date(2025, 9, 1), "buy_price": 100.0, "sell_price": 250.0, "quantity": 1000}, # LTCG ₹1.5L
    ]

    res = engine.calculate_portfolio_capital_gains_with_setoff(trades, tax_year_date=date(2025, 10, 1))

    assert res["era"] == "IT_ACT_1961"
    assert res["governing_setoff_section"] == "Section 70"
    assert res["net_stcg_taxable"] == 0.0
    assert res["stcg_tax_payable"] == 0.0
    assert res["net_ltcg_before_exemption"] == 130000.0
    assert res["ltcg_exemption_utilized"] == 125000.0
    assert res["taxable_ltcg"] == 5000.0
    assert res["ltcg_tax_payable"] == 625.0
    assert res["total_capital_gains_tax"] == 625.0
    assert res["carry_forward_losses"]["total_carry_forward"] == 0.0


def test_ltcl_strictly_prohibited_against_stcg():
    """
    Critical statutory test (Section 70(3) / Section 108(3)):
    LTCL = ₹1,00,000.
    STCG = ₹80,000.
    LTCG = ₹0.
    Statutory rule: LTCL CANNOT be set off against STCG!
    - Taxable STCG remains ₹80,000 @ 20% = ₹16,000.
    - Full LTCL of ₹1,00,000 is carried forward under Section 74 / Section 111.
    """
    engine = TaxEngine()
    trades = [
        {"buy_date": date(2024, 1, 1), "sell_date": date(2025, 6, 1), "buy_price": 200.0, "sell_price": 100.0, "quantity": 1000},  # LTCL ₹1,00,000
        {"buy_date": date(2025, 4, 1), "sell_date": date(2025, 8, 1), "buy_price": 100.0, "sell_price": 180.0, "quantity": 1000},  # STCG ₹80,000
    ]

    res = engine.calculate_portfolio_capital_gains_with_setoff(trades, tax_year_date=date(2025, 10, 1))

    assert res["net_stcg_taxable"] == 80000.0
    assert res["stcg_tax_payable"] == 16000.0
    assert res["taxable_ltcg"] == 0.0
    assert res["carry_forward_losses"]["ltcl"] == 100000.0
    assert res["carry_forward_losses"]["stcl"] == 0.0


def test_transition_to_it_act_2025_loss_rules():
    """
    Tests that after April 1, 2026 under the Income-tax Act, 2025:
    - Governing set-off section is Section 108
    - Governing carry-forward section is Section 111
    - Seamless transition of prior losses under Section 536
    """
    engine = TaxEngine()
    trades = [
        {"buy_date": date(2026, 4, 1), "sell_date": date(2026, 6, 1), "buy_price": 100.0, "sell_price": 80.0, "quantity": 500},   # STCL ₹10,000
        {"buy_date": date(2026, 4, 1), "sell_date": date(2026, 7, 1), "buy_price": 100.0, "sell_price": 150.0, "quantity": 500},  # STCG ₹25,000
    ]

    # Brought forward loss from 1961 era: ₹5,000 STCL
    res = engine.calculate_portfolio_capital_gains_with_setoff(
        trades,
        tax_year_date=date(2026, 8, 1),
        brought_forward_stcl=5000.0
    )

    assert res["era"] == "IT_ACT_2025"
    assert res["governing_setoff_section"] == "Section 108"
    assert res["governing_carryforward_section"] == "Section 111"
    # Current STCG 25k - Current STCL 10k = 15k - B/F STCL 5k = 10k taxable STCG
    assert res["net_stcg_taxable"] == 10000.0
    assert res["stcg_tax_payable"] == 2000.0  # 20% under Section 196
