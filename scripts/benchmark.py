"""Benchmark suite for execution performance measurement on local environment."""
import time
import sys
from datetime import date
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.bhavcopy import BhavcopyIngester
from src.core.adjustments import PriceAdjustmentEngine
from src.core.total_return import TotalReturnEngine


def benchmark_ingestion_and_adjustment():
    print("=== Running Local Benchmark ===")
    fixture_path = Path(__file__).parent.parent / "tests" / "fixtures" / "sample_bhavcopy.csv"
    with open(fixture_path, "rb") as f:
        csv_bytes = f.read()

    ingester = BhavcopyIngester()
    start_t = time.perf_counter()
    iterations = 250  # Simulates 1 year of daily trading files
    for i in range(iterations):
        fhash = ingester.compute_sha256(csv_bytes)
        records = ingester.parse_bhavcopy_csv(csv_bytes, "test.csv", fhash, date(2024, 1, 5))
    elapsed_ingest = time.perf_counter() - start_t
    print(f"[Benchmark] Bhavcopy Hash + Parse (250 iterations): {elapsed_ingest:.4f} seconds (Target < 120s)")

    # Benchmark Price Adjustment & TR on 1,000 synthetic trading days
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
    print(f"[Benchmark] 5-Year Adjustment Calculation (50 runs): {elapsed_adj:.4f} seconds (Avg: {elapsed_adj/50*1000:.2f} ms)")


if __name__ == "__main__":
    benchmark_ingestion_and_adjustment()
