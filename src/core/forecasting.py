"""Quantitative Forecasting and Monte Carlo Scenario Engine.
Uses stationary block bootstrapping on historical weekly log returns to preserve
volatility clustering, kurtosis, and tail-risk dependencies without Gaussian assumptions.
"""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd


@dataclass
class SimulationResults:
    current_price: float
    projection_horizon_weeks: int
    n_simulations: int
    p5_final: float
    p25_final: float
    p50_final: float
    p75_final: float
    p95_final: float
    prob_positive_return: float
    median_max_drawdown_pct: float
    p5_trajectory: List[float]
    p50_trajectory: List[float]
    p95_trajectory: List[float]


class ForecastingEngine:
    """Simulates medium to long term stock price distributions using block bootstrapping."""

    @staticmethod
    def run_block_bootstrap_simulation(
        price_series: pd.Series,
        horizon_weeks: int = 52,     # 1 year default
        n_simulations: int = 1000,
        block_size_weeks: int = 4,   # 4-week blocks to capture monthly momentum/clustering
        random_seed: Optional[int] = 42
    ) -> SimulationResults:
        """
        Runs stationary block bootstrap Monte Carlo:
        1. Resamples weekly returns in contiguous blocks.
        2. Compounds paths from current price.
        3. Computes 5th, 25th, 50th, 75th, 95th percentiles and drawdown stats.
        """
        if random_seed is not None:
            np.random.seed(random_seed)

        prices = price_series.dropna().values
        if len(prices) < 20:
            raise ValueError(f"Need at least 20 historical price points for bootstrapping, got {len(prices)}")

        current_price = float(prices[-1])

        # Convert daily/weekly series to weekly log returns if daily
        # If input has many data points, sample weekly or compute returns directly
        # Here we compute period log returns
        log_rets = np.diff(np.log(prices))
        n_rets = len(log_rets)

        if n_rets < block_size_weeks:
            block_size = max(1, n_rets // 2)
        else:
            block_size = block_size_weeks

        # Generate simulation paths
        num_blocks_needed = int(np.ceil(horizon_weeks / block_size))
        all_paths = np.zeros((n_simulations, horizon_weeks + 1))
        all_paths[:, 0] = current_price
        max_drawdowns = np.zeros(n_simulations)

        for s in range(n_simulations):
            # Pick random starting indices for blocks
            start_indices = np.random.randint(0, n_rets - block_size + 1, size=num_blocks_needed)
            sampled_rets = []
            for idx in start_indices:
                sampled_rets.extend(log_rets[idx : idx + block_size])
            sampled_rets = np.array(sampled_rets[:horizon_weeks])

            # Compound prices
            cumulative_log_ret = np.cumsum(sampled_rets)
            path_prices = current_price * np.exp(cumulative_log_ret)
            all_paths[s, 1:] = path_prices

            # Compute maximum drawdown for this path
            full_path = all_paths[s, :]
            running_max = np.maximum.accumulate(full_path)
            drawdowns = (running_max - full_path) / running_max
            max_drawdowns[s] = np.max(drawdowns)

        # Calculate percentiles across paths at each time step
        p5_traj = np.percentile(all_paths, 5, axis=0)
        p25_traj = np.percentile(all_paths, 25, axis=0)
        p50_traj = np.percentile(all_paths, 50, axis=0)
        p75_traj = np.percentile(all_paths, 75, axis=0)
        p95_traj = np.percentile(all_paths, 95, axis=0)

        final_prices = all_paths[:, -1]
        prob_positive = float(np.mean(final_prices > current_price))
        median_mdd = float(np.median(max_drawdowns) * 100.0)

        return SimulationResults(
            current_price=round(current_price, 2),
            projection_horizon_weeks=horizon_weeks,
            n_simulations=n_simulations,
            p5_final=round(float(p5_traj[-1]), 2),
            p25_final=round(float(p25_traj[-1]), 2),
            p50_final=round(float(p50_traj[-1]), 2),
            p75_final=round(float(p75_traj[-1]), 2),
            p95_final=round(float(p95_traj[-1]), 2),
            prob_positive_return=round(prob_positive, 4),
            median_max_drawdown_pct=round(median_mdd, 2),
            p5_trajectory=[round(float(x), 2) for x in p5_traj],
            p50_trajectory=[round(float(x), 2) for x in p50_traj],
            p95_trajectory=[round(float(x), 2) for x in p95_traj]
        )
