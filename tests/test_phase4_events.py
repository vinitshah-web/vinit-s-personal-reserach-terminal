"""Acceptance tests for Phase 4: Governance, Corporate Events, and Event Studies.
Tests MacKinlay event study with injected abnormal returns, statistical significance,
and qualitative governance risk scoring.
"""
from datetime import date, timedelta
import pytest
import pandas as pd
import numpy as np
from src.core.events import EventStudyEngine, GovernanceRiskEvaluator


def test_event_study_injected_abnormal_return():
    """
    Constructs an independent numerical fixture:
    - 100 trading days.
    - Market daily return has mean 0.0005, std 0.01.
    - Stock daily return = Market return + N(0, 0.005) (beta = 1.0, alpha = 0.0).
    - On Event Date (day 80), stock jumps by exactly +5.0% abnormally.
    - Asserts CAR in [-2, +2] window captures the +5.0% jump and t-statistic is statistically significant.
    """
    np.random.seed(42)
    n_days = 100
    start_date = date(2025, 1, 1)
    dates = [start_date + timedelta(days=i) for i in range(n_days)]

    # Market series starting at 10000
    market_rets = np.random.normal(loc=0.0002, scale=0.008, size=n_days)
    market_prices = [10000.0]
    for r in market_rets[1:]:
        market_prices.append(market_prices[-1] * (1.0 + r))

    # Stock series starting at 100, beta=1.0, noise std=0.003
    stock_noise = np.random.normal(loc=0.0, scale=0.003, size=n_days)
    stock_rets = market_rets + stock_noise

    # Inject +5.0% abnormal shock on day 80
    event_day_idx = 80
    stock_rets[event_day_idx] += 0.0500

    stock_prices = [100.0]
    for r in stock_rets[1:]:
        stock_prices.append(stock_prices[-1] * (1.0 + r))

    stock_df = pd.DataFrame({"trade_date": dates, "close_adj": stock_prices})
    market_df = pd.DataFrame({"trade_date": dates, "close": market_prices})

    event_date = dates[event_day_idx]
    result = EventStudyEngine.run_event_study(
        stock_prices=stock_df,
        market_prices=market_df,
        event_date=event_date,
        event_window=(-2, 2),
        estimation_window_len=60,
        buffer_days=5
    )

    # Beta should be close to 1.0
    assert abs(result.beta - 1.0) < 0.15

    # CAR in [-2, +2] window should be close to +5.0% (0.050)
    assert abs(result.car - 0.050) < 0.015
    assert result.t_stat > 3.0, f"Expected statistically significant t-stat > 3.0, got {result.t_stat}"
    assert result.p_value < 0.01, f"Expected p-value < 0.01, got {result.p_value}"
    assert len(result.daily_ar) == 5  # [-2, -1, 0, +1, +2]


def test_governance_risk_promoter_pledging():
    # Low pledge (5%)
    res_low = GovernanceRiskEvaluator.assess_promoter_pledging(5.0)
    assert res_low["risk_level"] == "LOW"
    assert res_low["governance_score"] == 90.0

    # Moderate pledge (20%)
    res_mod = GovernanceRiskEvaluator.assess_promoter_pledging(20.0)
    assert res_mod["risk_level"] == "MODERATE"
    assert res_mod["governance_score"] == 60.0

    # High pledge (40%)
    res_high = GovernanceRiskEvaluator.assess_promoter_pledging(40.0)
    assert res_high["risk_level"] == "HIGH"
    assert res_high["governance_score"] == 32.0

    # Severe pledge (65%)
    res_severe = GovernanceRiskEvaluator.assess_promoter_pledging(65.0)
    assert res_severe["risk_level"] == "SEVERE"
    assert res_severe["governance_score"] == 14.0

    # Invalid pledge values
    with pytest.raises(ValueError):
        GovernanceRiskEvaluator.assess_promoter_pledging(-5.0)
    with pytest.raises(ValueError):
        GovernanceRiskEvaluator.assess_promoter_pledging(105.0)


def test_governance_auditor_resignation():
    # Clean record
    res_clean = GovernanceRiskEvaluator.assess_auditor_resignation(0)
    assert res_clean["risk_level"] == "LOW"
    assert res_clean["score_deduction"] == 0

    # Single resignation
    res_single = GovernanceRiskEvaluator.assess_auditor_resignation(1, reason_flag="Disagreement on revenue recognition")
    assert res_single["risk_level"] == "HIGH"
    assert res_single["score_deduction"] == 30
    assert "revenue recognition" in res_single["status"]

    # Multiple resignations
    res_multi = GovernanceRiskEvaluator.assess_auditor_resignation(2)
    assert res_multi["risk_level"] == "CRITICAL"
    assert res_multi["score_deduction"] == 60
