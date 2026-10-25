"""Benchmark suite for execution performance measurement on local environment."""
import time
import sys
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
import numpy as np

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.bhavcopy import BhavcopyIngester
from src.core.adjustments import PriceAdjustmentEngine
from src.core.valuation import ValuationEngine
from src.core.forecasting import ForecastingEngine
from src.core.backtest import StrategyBacktestEngine, TradeOrder


def benchmark_suite():
    print("=== Running Comprehensive Performance Benchmark ===")
    fixture_path = Path(__file__).parent.parent / "tests" / "fixtures" / "sample_bhavcopy.csv"
    with open(fixture_path, "rb") as f:
        csv_bytes = f.read()

    # 1. Bhavcopy Hash + Parse
    ingester = BhavcopyIngester()
    start_t = time.perf_counter()
    iterations = 250  # Simulates 1 year of daily trading files
    for i in range(iterations):
        fhash = ingester.compute_sha256(csv_bytes)
        records = ingester.parse_bhavcopy_csv(csv_bytes, "test.csv", fhash, date(2024, 1, 5))
    elapsed_ingest = time.perf_counter() - start_t
    print(f"[Benchmark 1] Bhavcopy Hash + Parse (250 iterations): {elapsed_ingest:.4f}s (~{iterations/elapsed_ingest:.1f} files/sec)")

    # 2. 5-Year Adjustment Calculation
    synthetic_prices = [
        {"trade_date": date(2020, 1, 1), "close_raw": 100.0 + (i % 50), "volume_raw": 10000 + i * 10}
        for i in range(1250)
    ]
    actions = [
        {"action_type": "split", "ex_date": date(2021, 6, 1), "adj_factor": 0.50},
        {"action_type": "bonus", "ex_date": date(2022, 1, 1), "adj_factor": 0.666667},
        {"action_type": "rights", "ex_date": date(2023, 1, 1), "adj_factor": 0.90},
    ]
    adj_engine = PriceAdjustmentEngine()
    start_adj = time.perf_counter()
    for _ in range(50):
        df_adj = adj_engine.calculate_adjusted_series(synthetic_prices, actions)
    elapsed_adj = time.perf_counter() - start_adj
    print(f"[Benchmark 2] 5-Year Adjustment Series (50 runs): {elapsed_adj:.4f}s (Avg: {elapsed_adj/50*1000:.2f} ms/run)")

    # 3. Monte Carlo Block Bootstrap (1,000 paths, 52 weeks)
    price_series = pd.Series([1000.0 * (1.0 + 0.002)**i for i in range(100)])
    start_mc = time.perf_counter()
    mc_res = ForecastingEngine.run_block_bootstrap_simulation(
        price_series=price_series,
        horizon_weeks=52,
        n_simulations=1000,
        block_size_weeks=4
    )
    elapsed_mc = time.perf_counter() - start_mc
    print(f"[Benchmark 3] Monte Carlo Bootstrap (1,000 paths x 52 wks): {elapsed_mc:.4f}s (Target < 2.0s)")

    # 4. Reverse DCF Root Solving
    val_engine = ValuationEngine()
    start_rdcf = time.perf_counter()
    for _ in range(50):
        val_engine.solve_reverse_dcf(
            target_enterprise_value=919.6616,
            fcff_0=60.0,
            wacc=0.12,
            terminal_growth=0.04
        )
    elapsed_rdcf = time.perf_counter() - start_rdcf
    print(f"[Benchmark 4] Reverse DCF Solver (50 runs): {elapsed_rdcf:.4f}s (Avg: {elapsed_rdcf/50*1000:.2f} ms/solve)")

    # 5. Multi-Trade Strategy Backtesting with Full Statutory Tax Tracking
    bt_engine = StrategyBacktestEngine()
    trades = [
        TradeOrder(
            isin="INE002A01018",
            ticker="RELIANCE",
            buy_date=date(2025, 1, 1) + timedelta(days=i * 3),
            buy_price=2500.0 + (i % 20),
            sell_date=date(2025, 1, 1) + timedelta(days=i * 3 + 30),
            sell_price=2600.0 + (i % 30),
            quantity=100
        )
        for i in range(100)
    ]
    start_bt = time.perf_counter()
    bt_res = bt_engine.run_backtest(trades)
    elapsed_bt = time.perf_counter() - start_bt
    print(f"[Benchmark 5] Strategy Backtest (100 trades with STT, GST, Tax): {elapsed_bt:.4f}s (Avg: {elapsed_bt/100*1000:.2f} ms/trade)")
    print("=== Benchmark Suite Completed Successfully ===")


if __name__ == "__main__":
    benchmark_suite()
