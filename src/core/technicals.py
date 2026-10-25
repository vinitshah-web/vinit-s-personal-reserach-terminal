"""Technical Analysis, Volatility and Market Regime Engine.
All indicators are calculated STRICTLY on adjusted price series (never raw prices)
to ensure continuity across corporate action events (splits, bonuses, rights).
"""
from dataclasses import dataclass
from datetime import date
from typing import List, Dict, Optional, Any
import numpy as np
import pandas as pd


@dataclass
class TechnicalIndicators:
    dma_50: Optional[float]
    dma_200: Optional[float]
    dma_cross_signal: str       # "GOLDEN_CROSS", "DEATH_CROSS", "NEUTRAL"
    rsi_14: Optional[float]
    atr_14: Optional[float]
    rs_vs_index_126d: Optional[float]  # 6-month Relative Strength ratio


class TechnicalEngine:
    """Calculates quantitative technical indicators on adjusted price history."""

    @staticmethod
    def compute_sma(series: pd.Series, window: int) -> pd.Series:
        """Simple Moving Average."""
        return series.rolling(window=window, min_periods=window).mean()

    @staticmethod
    def compute_rsi_wilder(series: pd.Series, window: int = 14) -> pd.Series:
        """
        Relative Strength Index (RSI) using J. Welles Wilder Jr.'s smoothing.
        RSI = 100 - (100 / (1 + RS))
        RS = Smoothed Average Gain / Smoothed Average Loss
        """
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        # First average is simple mean of first `window` periods
        avg_gain = pd.Series(index=series.index, dtype=float)
        avg_loss = pd.Series(index=series.index, dtype=float)

        if len(series) < window + 1:
            return pd.Series(index=series.index, dtype=float)

        avg_gain.iloc[window] = gain.iloc[1:window + 1].mean()
        avg_loss.iloc[window] = loss.iloc[1:window + 1].mean()

        for i in range(window + 1, len(series)):
            avg_gain.iloc[i] = (avg_gain.iloc[i - 1] * (window - 1) + gain.iloc[i]) / window
            avg_loss.iloc[i] = (avg_loss.iloc[i - 1] * (window - 1) + loss.iloc[i]) / window

        rs = avg_gain / avg_loss
        # Where avg_loss is 0, RSI is 100
        rsi = 100.0 - (100.0 / (1.0 + rs))
        rsi = rsi.where(avg_loss != 0, 100.0)
        rsi = rsi.where(avg_gain != 0, 0.0)
        return rsi

    @staticmethod
    def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
        """
        Average True Range (ATR 14) using Wilder's smoothing.
        TR = max(High - Low, abs(High - PrevClose), abs(Low - PrevClose))
        """
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = pd.Series(index=close.index, dtype=float)
        if len(close) < window + 1:
            return atr

        atr.iloc[window] = tr.iloc[1:window + 1].mean()
        for i in range(window + 1, len(close)):
            atr.iloc[i] = (atr.iloc[i - 1] * (window - 1) + tr.iloc[i]) / window
        return atr

    @classmethod
    def evaluate_stock_technicals(
        cls,
        df_adj: pd.DataFrame,
        df_index: Optional[pd.DataFrame] = None
    ) -> TechnicalIndicators:
        """
        Computes snapshot of technical metrics on the latest available trading day.
        df_adj must contain 'trade_date', 'close_adj', 'high_adj', 'low_adj'.
        """
        df = df_adj.sort_values("trade_date").copy().reset_index(drop=True)
        if len(df) == 0:
            return TechnicalIndicators(None, None, "NEUTRAL", None, None, None)

        close = df["close_adj"]
        high = df.get("high_adj", close)
        low = df.get("low_adj", close)

        sma50 = cls.compute_sma(close, 50)
        sma200 = cls.compute_sma(close, 200)
        rsi = cls.compute_rsi_wilder(close, 14)
        atr = cls.compute_atr(high, low, close, 14)

        latest_50 = float(sma50.iloc[-1]) if pd.notna(sma50.iloc[-1]) else None
        latest_200 = float(sma200.iloc[-1]) if pd.notna(sma200.iloc[-1]) else None
        latest_rsi = float(round(rsi.iloc[-1], 2)) if pd.notna(rsi.iloc[-1]) else None
        latest_atr = float(round(atr.iloc[-1], 2)) if pd.notna(atr.iloc[-1]) else None

        # Cross detection
        cross_signal = "NEUTRAL"
        if len(sma50) >= 2 and pd.notna(sma50.iloc[-1]) and pd.notna(sma200.iloc[-1]) and pd.notna(sma50.iloc[-2]) and pd.notna(sma200.iloc[-2]):
            if sma50.iloc[-2] <= sma200.iloc[-2] and sma50.iloc[-1] > sma200.iloc[-1]:
                cross_signal = "GOLDEN_CROSS"
            elif sma50.iloc[-2] >= sma200.iloc[-2] and sma50.iloc[-1] < sma200.iloc[-1]:
                cross_signal = "DEATH_CROSS"

        # Relative strength vs benchmark index over 126 trading days (~6 months)
        rs_ratio = None
        if df_index is not None and len(df) >= 126 and len(df_index) >= 126:
            merged = pd.merge(
                df[["trade_date", "close_adj"]],
                df_index[["trade_date", "close"]].rename(columns={"close": "idx_close"}),
                on="trade_date"
            ).sort_values("trade_date")

            if len(merged) >= 126:
                stock_ret_6m = (merged["close_adj"].iloc[-1] / merged["close_adj"].iloc[-126]) - 1.0
                idx_ret_6m = (merged["idx_close"].iloc[-1] / merged["idx_close"].iloc[-126]) - 1.0
                # RS is ratio of total returns
                rs_ratio = round((1.0 + stock_ret_6m) / (1.0 + idx_ret_6m), 4)

        return TechnicalIndicators(
            dma_50=round(latest_50, 2) if latest_50 else None,
            dma_200=round(latest_200, 2) if latest_200 else None,
            dma_cross_signal=cross_signal,
            rsi_14=latest_rsi,
            atr_14=latest_atr,
            rs_vs_index_126d=rs_ratio
        )


class MarketRegimeEngine:
    """Classifies overarching Indian equity market regimes."""

    @staticmethod
    def classify_regime(df_index: pd.DataFrame) -> Dict[str, Any]:
        """
        Classifies regime using benchmark index (e.g. NIFTY 50):
        - 20-day annualized realized volatility: std(daily_ret) * sqrt(252)
        - Trend: Current Index vs 200-DMA
        Regimes:
        - BULL_QUIET: Index > 200-DMA and Vol < 15%
        - BULL_VOLATILE: Index > 200-DMA and Vol >= 15%
        - BEAR_VOLATILE: Index <= 200-DMA and Vol >= 18%
        - BEAR_QUIET: Index <= 200-DMA and Vol < 18%
        """
        df = df_index.sort_values("trade_date").copy().reset_index(drop=True)
        if len(df) < 200:
            raise ValueError(f"Need at least 200 index trading days to classify regime, got {len(df)}")

        close = df["close"]
        daily_ret = close.pct_change()
        vol_20d = float(daily_ret.iloc[-20:].std() * np.sqrt(252))

        dma_200 = float(close.iloc[-200:].mean())
        current_close = float(close.iloc[-1])
        trend = "BULL" if current_close > dma_200 else "BEAR"

        if trend == "BULL":
            regime = "BULL_QUIET" if vol_20d < 0.15 else "BULL_VOLATILE"
        else:
            regime = "BEAR_VOLATILE" if vol_20d >= 0.18 else "BEAR_QUIET"

        return {
            "regime": regime,
            "trend": trend,
            "index_close": current_close,
            "index_dma200": round(dma_200, 2),
            "realized_vol_20d_pct": round(vol_20d * 100.0, 2),
            "as_of_date": df["trade_date"].iloc[-1].isoformat() if hasattr(df["trade_date"].iloc[-1], 'isoformat') else str(df["trade_date"].iloc[-1])
        }
