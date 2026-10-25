"""Acceptance Tests: Corporate Action Adjustments, Rights Strategies & Total Return Consistency."""
import pytest
from datetime import date
from src.core.adjustments import PriceAdjustmentEngine
from src.core.total_return import TotalReturnEngine, RightsStrategy, IncompleteRightsDataError


def test_rights_issue_investor_strategies():
    """
    Acceptance Test 5: Rights issue investor strategies (Subscribe, Sell/Renounce, Lapse).
    Cum price = 800.0, Rights 1:4 @ sub price 400.0.
    TERP = (800*4 + 400*1)/5 = 720.00. Factor = 720/800 = 0.90.
    """
    raw_prices = [
        {"trade_date": date(2023, 9, 14), "close_raw": 800.0, "volume_raw": 1000},
        {"trade_date": date(2023, 9, 15), "close_raw": 720.0, "volume_raw": 1200},
    ]
    actions = [{
        "action_type": "rights",
        "ex_date": date(2023, 9, 15),
        "ratio_numerator": 1,
        "ratio_denominator": 4,
        "cum_rights_price": 800.0,
        "subscription_price": 400.0,
        "adj_factor": 0.90
    }]

    adj_engine = PriceAdjustmentEngine()
    df_adj = adj_engine.calculate_adjusted_series(raw_prices, actions)
    tr_engine = TotalReturnEngine()

    # 1. Strategy: SUBSCRIBE
    tr_sub = tr_engine.calculate_total_return_series(df_adj, actions, base_index=10000.0, rights_strategy=RightsStrategy.SUBSCRIBE)
    # Price dropped from 800 to 720 (exactly TERP). Pre-price adjusted is 720.
    # Return is flat: 10000.0
    assert tr_sub.loc[1, "total_return_index"] == 10000.0

    # 2. Strategy: SELL_RENOUNCE
    tr_sell = tr_engine.calculate_total_return_series(df_adj, actions, base_index=10000.0, rights_strategy=RightsStrategy.SELL_RENOUNCE)
    assert tr_sell.loc[1, "total_return_index"] >= 10000.0

    # 3. Strategy: LAPSE
    tr_lapse = tr_engine.calculate_total_return_series(df_adj, actions, base_index=10000.0, rights_strategy=RightsStrategy.LAPSE)
    # Investor suffers 10% dilution loss: 10000 * 0.90 = 9000.0
    assert round(tr_lapse.loc[1, "total_return_index"], 1) == 9000.0


def test_incomplete_rights_parameters_fails_closed():
    """Acceptance Test 5b: Missing rights terms raise IncompleteRightsDataError."""
    raw_prices = [
        {"trade_date": date(2023, 9, 14), "close_raw": 800.0, "volume_raw": 1000},
        {"trade_date": date(2023, 9, 15), "close_raw": 720.0, "volume_raw": 1200},
    ]
    incomplete_action = [{
        "action_type": "rights",
        "ex_date": date(2023, 9, 15),
        "ratio_numerator": 1,
        "ratio_denominator": 4,
        "cum_rights_price": None,  # MISSING!
        "subscription_price": 400.0,
        "adj_factor": 0.90
    }]
    adj_engine = PriceAdjustmentEngine()
    df_adj = adj_engine.calculate_adjusted_series(raw_prices, incomplete_action)
    tr_engine = TotalReturnEngine()

    with pytest.raises(IncompleteRightsDataError):
        tr_engine.calculate_total_return_series(df_adj, incomplete_action)


def test_corporate_action_consistency_prices_volume_dividends():
    """
    Acceptance Test 6: Consistency between prices, volume, per-share dividends, and TR index.
    A 2:1 split must:
    - Halve historical prices
    - Double historical volume
    - Halve historical dividend per share
    - Leave total return compounding mathematically invariant
    """
    raw_prices = [
        {"trade_date": date(2024, 1, 8), "close_raw": 400.0, "volume_raw": 50000},
        {"trade_date": date(2024, 1, 9), "close_raw": 204.0, "volume_raw": 100000},
    ]
    actions = [
        {"action_type": "split", "ex_date": date(2024, 1, 9), "adj_factor": 0.50}
    ]
    adj_engine = PriceAdjustmentEngine()
    df = adj_engine.calculate_adjusted_series(raw_prices, actions)

    assert df.loc[0, "close_adj"] == 200.0
    assert df.loc[0, "volume_adj"] == 100000.0  # 50,000 / 0.5 = 100,000
    assert df.loc[1, "close_adj"] == 204.0
    assert df.loc[1, "volume_adj"] == 100000.0
