"""Corporate Governance and Event Study Analysis Engine.
Implements MacKinlay (1997) event study methodology:
- Market Model (OLS alpha, beta) and Market-Adjusted Model
- Abnormal Returns (AR) and Cumulative Abnormal Returns (CAR)
- Statistical significance testing (t-statistic, p-value)
- Governance risk scoring (promoter pledges, auditor resignations)
"""
from dataclasses import dataclass
from datetime import date, datetime
import math
from typing import List, Dict, Optional, Tuple, Any
import numpy as np
import pandas as pd


@dataclass
class EventStudyResult:
    isin: str
    event_date: date
    event_window_start: int  # e.g. -2
    event_window_end: int    # e.g. +2
    alpha: float
    beta: float
    car: float               # Cumulative Abnormal Return (decimal, e.g. 0.05 for +5%)
    car_pct: float           # Cumulative Abnormal Return in percent (e.g. 5.0%)
    t_stat: float            # t-statistic of CAR
    p_value: float           # two-tailed p-value
    daily_ar: List[Dict[str, float]]  # list of {day: t, ar: abnormal_return, car: cumulative_ar}


class EventStudyEngine:
    """
    Computes Abnormal Returns and CAR surrounding corporate events.
    Strictly uses adjusted prices to avoid dividend/split distortions.
    """

    @staticmethod
    def run_event_study(
        stock_prices: pd.DataFrame,   # DataFrame with ['trade_date', 'close_adj']
        market_prices: pd.DataFrame,  # DataFrame with ['trade_date', 'close']
        event_date: date,
        event_window: Tuple[int, int] = (-2, 2),
        estimation_window_len: int = 60,
        buffer_days: int = 5
    ) -> EventStudyResult:
        """
        Runs an institutional event study:
        - Estimation window: [-estimation_window_len - buffer_days, -buffer_days] relative to event_date.
        - Event window: [event_window[0], event_window[1]].
        """
        # Merge stock and market prices on trade_date
        merged = pd.merge(
            stock_prices[['trade_date', 'close_adj']],
            market_prices[['trade_date', 'close']].rename(columns={'close': 'market_close'}),
            on='trade_date',
            how='inner'
        ).sort_values('trade_date').reset_index(drop=True)

        if len(merged) < estimation_window_len + (event_window[1] - event_window[0]) + 10:
            raise ValueError(f"Insufficient price history for event study: need at least {estimation_window_len + 30} days, got {len(merged)}")

        # Calculate daily returns
        merged['stock_ret'] = merged['close_adj'].pct_change()
        merged['market_ret'] = merged['market_close'].pct_change()
        merged = merged.dropna().reset_index(drop=True)

        # Find the event date index in trading days
        event_indices = merged.index[merged['trade_date'] >= event_date].tolist()
        if not event_indices:
            raise ValueError(f"Event date {event_date} is after available price history.")
        event_idx = event_indices[0]

        # Define index ranges
        w_start, w_end = event_window
        ev_start_idx = event_idx + w_start
        ev_end_idx = event_idx + w_end

        est_end_idx = event_idx - buffer_days
        est_start_idx = est_end_idx - estimation_window_len

        if est_start_idx < 0:
            raise ValueError(f"Not enough historical data prior to event date {event_date} for {estimation_window_len}-day estimation window.")

        if ev_end_idx >= len(merged):
            raise ValueError(f"Not enough forward data after event date {event_date} for event window.")

        # Estimation window data
        est_df = merged.iloc[est_start_idx:est_end_idx]
        x = est_df['market_ret'].values
        y = est_df['stock_ret'].values

        # OLS regression: y = alpha + beta * x
        cov_matrix = np.cov(x, y)
        var_x = cov_matrix[0, 0]
        cov_xy = cov_matrix[0, 1]

        if var_x > 1e-12:
            beta = cov_xy / var_x
            alpha = np.mean(y) - beta * np.mean(x)
        else:
            beta = 1.0
            alpha = 0.0

        # Residual variance in estimation window
        residuals = y - (alpha + beta * x)
        degrees_of_freedom = max(len(residuals) - 2, 1)
        sigma2_eps = np.sum(residuals ** 2) / degrees_of_freedom

        # Event window data
        event_df = merged.iloc[ev_start_idx:ev_end_idx + 1].copy()
        event_df['expected_ret'] = alpha + beta * event_df['market_ret']
        event_df['abnormal_ret'] = event_df['stock_ret'] - event_df['expected_ret']

        daily_ar = []
        running_car = 0.0
        for i, row in enumerate(event_df.itertuples()):
            day_offset = w_start + i
            ar = float(row.abnormal_ret)
            running_car += ar
            daily_ar.append({
                "day_offset": day_offset,
                "trade_date": row.trade_date.isoformat() if hasattr(row.trade_date, 'isoformat') else str(row.trade_date),
                "stock_ret": float(row.stock_ret),
                "market_ret": float(row.market_ret),
                "abnormal_ret": ar,
                "car": running_car
            })

        total_car = running_car
        window_len = (w_end - w_start + 1)
        var_car = window_len * sigma2_eps
        se_car = math.sqrt(max(var_car, 1e-12))
        t_stat = total_car / se_car

        # Approximate two-tailed p-value using normal distribution for sample sizes > 30
        p_val = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(t_stat) / math.sqrt(2.0))))

        return EventStudyResult(
            isin="N/A",
            event_date=event_date,
            event_window_start=w_start,
            event_window_end=w_end,
            alpha=float(alpha),
            beta=float(beta),
            car=float(total_car),
            car_pct=float(round(total_car * 100.0, 4)),
            t_stat=float(round(t_stat, 4)),
            p_value=float(round(p_val, 6)),
            daily_ar=daily_ar
        )


class GovernanceRiskEvaluator:
    """Evaluates qualitative and quantitative corporate governance risks."""

    @staticmethod
    def assess_promoter_pledging(pledge_pct: float) -> Dict[str, Any]:
        """
        Evaluates promoter share encumbrance / pledge risk:
        - 0% - 10%: LOW
        - 10% - 25%: MODERATE
        - 25% - 50%: HIGH
        - > 50%: SEVERE (Significant margin-call liquidation risk)
        """
        if pledge_pct < 0.0 or pledge_pct > 100.0:
            raise ValueError(f"Invalid pledge percentage {pledge_pct}%: must be between 0 and 100.")

        if pledge_pct <= 10.0:
            risk_level = "LOW"
            score = 100 - (pledge_pct * 2.0)
            notes = "Minimal pledge risk; promoters retain unrestricted voting and disposal discretion."
        elif pledge_pct <= 25.0:
            risk_level = "MODERATE"
            score = 80 - ((pledge_pct - 10.0) * 2.0)
            notes = "Moderate encumbrance; monitor debt servicing and collateral coverage ratios."
        elif pledge_pct <= 50.0:
            risk_level = "HIGH"
            score = 50 - ((pledge_pct - 25.0) * 1.2)
            notes = "High pledge level; susceptible to forced selling during sharp market drawdowns."
        else:
            risk_level = "SEVERE"
            score = max(20 - ((pledge_pct - 50.0) * 0.4), 0.0)
            notes = "Critical risk: over half of promoter holding encumbered. Severe governance discount warranted."

        return {
            "pledge_pct": pledge_pct,
            "risk_level": risk_level,
            "governance_score": round(score, 2),
            "notes": notes
        }

    @staticmethod
    def assess_auditor_resignation(resignation_count_3yr: int, reason_flag: Optional[str] = None) -> Dict[str, Any]:
        """Evaluates statutory auditor turnover risk."""
        if resignation_count_3yr == 0:
            return {"risk_level": "LOW", "score_deduction": 0, "status": "CLEAN"}
        elif resignation_count_3yr == 1:
            return {
                "risk_level": "HIGH",
                "score_deduction": 30,
                "status": f"Auditor resigned prematurely ({reason_flag or 'unspecified reason'}). Red flag under SEBI LODR."
            }
        else:
            return {
                "risk_level": "CRITICAL",
                "score_deduction": 60,
                "status": f"Multiple ({resignation_count_3yr}) auditor resignations in 3 years. Severe forensic caution."
            }
