"""Acceptance tests for Phase 6: Technicals, Volatility & Market Regime Engine.
Verifies corporate action distortion immunity on adjusted prices, Wilder RSI,
and Market Regime Classification on actual NIFTY 50 index prices.
"""
from datetime import date, timedelta
import pytest
import pandas as pd
import numpy as np
from src.core.technicals import TechnicalEngine, MarketRegimeEngine


def test_dma_immunity_to_bonus_split_distortion():
    """
    Critical quantitative test:
    A stock trades at ₹1,000 for 210 days.
    On day 211, a 1:1 bonus issue takes place. Raw price drops from ₹1,000 to ₹500.
    In the unadjusted series, 200-DMA would plunge artificially.
    In our adjusted price series (where adjustment factor F=0.5 prior to bonus):
    All pre-bonus adjusted prices are ₹500.0, post-bonus adjusted prices are ₹500.0.
    200-DMA must remain exactly ₹500.0 with 0.0% artificial drop!
    """
    n_days = 220
    start_date = date(2025, 1, 1)
    dates = [start_date + timedelta(days=i) for i in range(n_days)]

    # Raw prices: 1000 for days 0-210, 500 for days 211-219
    raw_prices = [1000.0] * 211 + [500.0] * 9

    # Adjusted prices: all 500.0
    adj_prices = [500.0] * n_days

    df_stock = pd.DataFrame({
        "trade_date": dates,
        "close_raw": raw_prices,
        "close_adj": adj_prices,
        "high_adj": adj_prices,
        "low_adj": adj_prices
    })

    # Technicals computed on adjusted series
    indicators = TechnicalEngine.evaluate_stock_technicals(df_stock)

    assert indicators.dma_200 == 500.0, f"Expected 200-DMA to be exactly 500.0, got {indicators.dma_200}"
    assert indicators.dma_50 == 500.0, f"Expected 50-DMA to be exactly 500.0, got {indicators.dma_50}"
    assert indicators.dma_cross_signal == "NEUTRAL"


def test_rsi_wilder_bounds_and_response():
    """Verifies Wilder RSI bounds between 0 and 100."""
    n_days = 50
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(n_days)]

    # Strictly rising price series: 100 to 150
    rising_prices = [100.0 + i * 1.0 for i in range(n_days)]
    df_rising = pd.DataFrame({
        "trade_date": dates,
        "close_adj": rising_prices,
        "high_adj": rising_prices,
        "low_adj": rising_prices
    })
    ind_rising = TechnicalEngine.evaluate_stock_technicals(df_rising)
    assert ind_rising.rsi_14 == 100.0  # Zero loss days -> RSI 100

    # Strictly falling price series: 100 down to 50
    falling_prices = [100.0 - i * 1.0 for i in range(n_days)]
    df_falling = pd.DataFrame({
        "trade_date": dates,
        "close_adj": falling_prices,
        "high_adj": falling_prices,
        "low_adj": falling_prices
    })
    ind_falling = TechnicalEngine.evaluate_stock_technicals(df_falling)
    assert ind_falling.rsi_14 == 0.0  # Zero gain days -> RSI 0


def test_market_regime_classification_real_nifty50():
    """Tests regime classifier on the 247-day real NIFTY 50 dataset."""
    df_idx = pd.read_csv("NIFTY 50-25-10-2025-to-25-10-2026.csv")
    df_idx.columns = [c.strip() for c in df_idx.columns]
    df_idx = df_idx.rename(columns={"Date": "trade_date", "Close": "close"})
    df_idx["trade_date"] = pd.to_datetime(df_idx["trade_date"], format="%d-%b-%Y").dt.date

    # Reverse chronologically to ascending
    df_idx = df_idx.sort_values("trade_date").reset_index(drop=True)

    regime_res = MarketRegimeEngine.classify_regime(df_idx)

    assert regime_res["regime"] in ["BULL_QUIET", "BULL_VOLATILE", "BEAR_VOLATILE", "BEAR_QUIET"]
    assert regime_res["trend"] in ["BULL", "BEAR"]
    assert regime_res["index_close"] == 22600.0  # Latest close on 23-OCT-2026
    assert regime_res["index_dma200"] > 20000.0
    assert 5.0 <= regime_res["realized_vol_20d_pct"] <= 50.0  # Realized vol in sensible institutional range
