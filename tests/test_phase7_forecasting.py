"""Acceptance tests for Phase 7: Quantitative Forecasting & Monte Carlo Simulation.
Verifies stationary block bootstrapping, monotonic percentile ordering, and drawdown metrics.
"""
import pytest
import pandas as pd
import numpy as np
from src.core.forecasting import ForecastingEngine, SimulationResults


def test_monte_carlo_block_bootstrap_percentiles():
    np.random.seed(101)
    # Generate 100 historical weekly prices with slight upward drift
    weekly_rets = np.random.normal(loc=0.002, scale=0.03, size=100)
    prices = [1000.0]
    for r in weekly_rets:
        prices.append(prices[-1] * (1.0 + r))

    price_series = pd.Series(prices)

    res = ForecastingEngine.run_block_bootstrap_simulation(
        price_series=price_series,
        horizon_weeks=52,
        n_simulations=500,
        block_size_weeks=4,
        random_seed=42
    )

    assert isinstance(res, SimulationResults)
    assert res.current_price == round(prices[-1], 2)
    assert res.projection_horizon_weeks == 52
    assert res.n_simulations == 500

    # Monotonic percentile order: P5 <= P25 <= P50 <= P75 <= P95
    assert res.p5_final < res.p25_final
    assert res.p25_final <= res.p50_final
    assert res.p50_final <= res.p75_final
    assert res.p75_final < res.p95_final

    # Probability of positive return must be in [0, 1]
    assert 0.0 <= res.prob_positive_return <= 1.0

    # Median max drawdown must be positive
    assert res.median_max_drawdown_pct >= 0.0

    # Trajectories length must equal horizon + 1 (53 weeks)
    assert len(res.p5_trajectory) == 53
    assert len(res.p50_trajectory) == 53
    assert len(res.p95_trajectory) == 53
    assert res.p5_trajectory[0] == res.current_price
    assert res.p50_trajectory[0] == res.current_price


def test_insufficient_history_fails_closed():
    short_series = pd.Series([100.0, 102.0, 101.0])
    with pytest.raises(ValueError):
        ForecastingEngine.run_block_bootstrap_simulation(short_series)
