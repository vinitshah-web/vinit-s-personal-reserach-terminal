"""Tests for Phase 1: Total Return Index with Dividend Reinvestment."""
import pytest
from datetime import date
from src.core.adjustments import PriceAdjustmentEngine
from src.core.total_return import TotalReturnEngine


def test_fixture_7_dividend_followed_by_split():
    """
    Fixture 7:
    Day 1: close_raw 500.00
    Day 2: close_raw 490.00, Div 10.00
    Day 3: close_raw 495.00
    Day 4: close_raw 500.00
    Day 5: close_raw 252.00 (Split 2:1 ex-date)
    Day 6: close_raw 255.00
    """
    raw_prices = [
        {"trade_date": date(2024, 1, 8), "close_raw": 500.00, "volume_raw": 1000},
        {"trade_date": date(2024, 1, 9), "close_raw": 490.00, "volume_raw": 1000},
        {"trade_date": date(2024, 1, 10), "close_raw": 495.00, "volume_raw": 1000},
        {"trade_date": date(2024, 1, 11), "close_raw": 500.00, "volume_raw": 1000},
        {"trade_date": date(2024, 1, 12), "close_raw": 252.00, "volume_raw": 2000},
        {"trade_date": date(2024, 1, 15), "close_raw": 255.00, "volume_raw": 2000},
    ]
    actions = [
        {"action_type": "dividend_cash", "ex_date": date(2024, 1, 9), "dividend_per_share": 10.0, "adj_factor": None},
        {"action_type": "split", "ex_date": date(2024, 1, 12), "dividend_per_share": None, "adj_factor": 0.50}
    ]

    adj_engine = PriceAdjustmentEngine()
    adj_df = adj_engine.calculate_adjusted_series(raw_prices, actions)

    tr_engine = TotalReturnEngine()
    tr_df = tr_engine.calculate_total_return_series(adj_df, actions, base_index=10000.0)

    # Verify Day 1
    assert tr_df.loc[0, "total_return_index"] == 10000.0
    # Day 2: price dropped by dividend -> TR is flat
    assert round(tr_df.loc[1, "total_return_index"], 4) == 10000.0
    # Day 3: 10102.0408
    assert round(tr_df.loc[2, "total_return_index"], 4) == 10102.0408
    # Day 4: 10204.0816
    assert round(tr_df.loc[3, "total_return_index"], 4) == 10204.0816
    # Day 5: 10285.7143
    assert round(tr_df.loc[4, "total_return_index"], 4) == 10285.7143
    # Day 6: 10408.1633
    assert round(tr_df.loc[5, "total_return_index"], 4) == 10408.1633


def test_fixture_8_bonus_followed_by_dividend():
    """
    Fixture 8:
    Day 1: close_raw 800.00
    Day 2: 1:1 Bonus ex-date (close_raw 405.00)
    Day 3: close_raw 410.00
    Day 4: close_raw 415.00
    Day 5: Ex-dividend (close_raw 410.00, Div 3.00)
    Day 6: close_raw 420.00
    """
    raw_prices = [
        {"trade_date": date(2024, 2, 5), "close_raw": 800.00, "volume_raw": 1000},
        {"trade_date": date(2024, 2, 6), "close_raw": 405.00, "volume_raw": 2000},
        {"trade_date": date(2024, 2, 7), "close_raw": 410.00, "volume_raw": 2000},
        {"trade_date": date(2024, 2, 8), "close_raw": 415.00, "volume_raw": 2000},
        {"trade_date": date(2024, 2, 9), "close_raw": 410.00, "volume_raw": 2000},
        {"trade_date": date(2024, 2, 12), "close_raw": 420.00, "volume_raw": 2000},
    ]
    actions = [
        {"action_type": "bonus", "ex_date": date(2024, 2, 6), "dividend_per_share": None, "adj_factor": 0.50},
        {"action_type": "dividend_cash", "ex_date": date(2024, 2, 9), "dividend_per_share": 3.0, "adj_factor": None}
    ]

    adj_engine = PriceAdjustmentEngine()
    adj_df = adj_engine.calculate_adjusted_series(raw_prices, actions)

    tr_engine = TotalReturnEngine()
    tr_df = tr_engine.calculate_total_return_series(adj_df, actions, base_index=10000.0)

    # Day 1: 10000.0
    assert tr_df.loc[0, "total_return_index"] == 10000.0
    # Day 2: 10125.0
    assert tr_df.loc[1, "total_return_index"] == 10125.0
    # Day 3: 10250.0
    assert tr_df.loc[2, "total_return_index"] == 10250.0
    # Day 4: 10375.0
    assert tr_df.loc[3, "total_return_index"] == 10375.0
    # Day 5: 10375 * 413 / 415 = 10325.0000 (Independently audited!)
    assert round(tr_df.loc[4, "total_return_index"], 4) == 10325.0
    # Day 6: 10325 * 420 / 410 = 10576.8293
    assert round(tr_df.loc[5, "total_return_index"], 4) == 10576.8293
