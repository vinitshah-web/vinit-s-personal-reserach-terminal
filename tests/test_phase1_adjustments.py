"""Tests for Phase 1: Corporate action price adjustment and factor derivation."""
import pytest
from datetime import date
from src.ingestion.corporate_actions import CorporateActionParser
from src.core.adjustments import PriceAdjustmentEngine


def test_split_factor_calculation():
    parser = CorporateActionParser()
    # 5:1 split -> factor = 1/5 = 0.20
    assert parser.compute_split_factor(5, 1) == 0.20
    # 2:1 split -> factor = 1/2 = 0.50
    assert parser.compute_split_factor(2, 1) == 0.50


def test_bonus_factor_calculation():
    parser = CorporateActionParser()
    # 1:2 bonus (1 bonus for 2 held) -> 2 / (2 + 1) = 2/3
    factor = parser.compute_bonus_factor(1, 2)
    assert round(factor, 6) == round(2 / 3, 6)


def test_rights_issue_terp_calculation():
    parser = CorporateActionParser()
    # Cum price 800, sub price 400, ratio 1:4 (1 new for 4 held)
    # TERP = (800*4 + 400*1)/5 = 3600/5 = 720.00
    # Factor = 720 / 800 = 0.90
    factor = parser.compute_rights_terp_factor(
        cum_rights_price=800.0,
        subscription_price=400.0,
        new_shares=1,
        old_shares=4
    )
    assert factor == 0.90


def test_fixture_1_split_5_to_1():
    """Fixture 1: 5:1 split on 2023-03-30."""
    prices = [
        {"trade_date": date(2023, 3, 28), "close_raw": 500.0, "volume_raw": 1000},
        {"trade_date": date(2023, 3, 29), "close_raw": 510.0, "volume_raw": 1100},
        {"trade_date": date(2023, 3, 30), "close_raw": 103.0, "volume_raw": 5200},
        {"trade_date": date(2023, 3, 31), "close_raw": 105.0, "volume_raw": 5000},
    ]
    actions = [
        {"action_type": "split", "ex_date": date(2023, 3, 30), "adj_factor": 0.20}
    ]
    engine = PriceAdjustmentEngine()
    df = engine.calculate_adjusted_series(prices, actions)

    # Pre-split dates should be multiplied by 0.20
    assert df.loc[0, "close_adj"] == 100.0
    assert df.loc[1, "close_adj"] == 102.0
    # Post-split dates should remain unadjusted (factor 1.0)
    assert df.loc[2, "close_adj"] == 103.0
    assert df.loc[3, "close_adj"] == 105.0
    # Volume should be divided by 0.20 for pre-split dates
    assert df.loc[0, "volume_adj"] == 5000.0


def test_fixture_2_bonus_1_to_2():
    """Fixture 2: 1:2 bonus on 2023-06-16."""
    factor = 2.0 / 3.0
    prices = [
        {"trade_date": date(2023, 6, 14), "close_raw": 900.0, "volume_raw": 1000},
        {"trade_date": date(2023, 6, 15), "close_raw": 910.0, "volume_raw": 1050},
        {"trade_date": date(2023, 6, 16), "close_raw": 612.0, "volume_raw": 1600},
    ]
    actions = [
        {"action_type": "bonus", "ex_date": date(2023, 6, 16), "adj_factor": factor}
    ]
    engine = PriceAdjustmentEngine()
    df = engine.calculate_adjusted_series(prices, actions)

    assert df.loc[0, "close_adj"] == 600.0  # 900 * 2/3
    assert round(df.loc[1, "close_adj"], 4) == round(910.0 * 2.0 / 3.0, 4)
    assert df.loc[2, "close_adj"] == 612.0
