"""Quantitative Medium-Term Strategy Backtesting and Tax Simulation Engine.
Applies exact statutory transaction costs (STT, Stamp Duty, Brokerage, Exchange charges, GST 18%)
and post-trade tax calculations (IT Act 1961 / 2025, LTCG exemption tracking per tax year).
"""
from dataclasses import dataclass, field
from datetime import date
from typing import List, Dict, Any, Optional
from src.tax.engine import TaxEngine


@dataclass
class TradeOrder:
    isin: str
    ticker: str
    buy_date: date
    buy_price: float
    sell_date: date
    sell_price: float
    quantity: int
    slippage_bps: float = 5.0  # 5 basis points (0.05%) default slippage


@dataclass
class TradeExecutionReport:
    isin: str
    ticker: str
    buy_date: date
    sell_date: date
    quantity: int
    buy_price_effective: float
    sell_price_effective: float
    buy_turnover: float
    sell_turnover: float
    gross_pnl: float
    stt_total: float
    stamp_duty: float
    brokerage_total: float
    exchange_charges: float
    sebi_charges: float
    gst_total: float
    slippage_cost: float
    total_friction: float
    net_pretax_pnl: float
    gain_type: str              # "STCG" or "LTCG"
    taxable_gain: float
    tax_rate: float
    tax_payable: float
    net_posttax_pnl: float


@dataclass
class PortfolioBacktestResult:
    trades_count: int
    profitable_trades: int
    win_rate_pct: float
    total_gross_pnl: float
    total_stt: float
    total_stamp_duty: float
    total_brokerage: float
    total_exchange_sebi_charges: float
    total_gst: float
    total_slippage: float
    total_friction_costs: float
    net_pretax_pnl: float
    total_tax_payable: float
    net_posttax_pnl: float
    trade_reports: List[TradeExecutionReport] = field(default_factory=list)


class StrategyBacktestEngine:
    """Executes backtests with exact transaction friction and dual-era statutory taxation."""

    def __init__(self, tax_engine: Optional[TaxEngine] = None):
        self.tax_engine = tax_engine or TaxEngine()

    @staticmethod
    def _get_tax_year(d: date) -> str:
        """Determines the tax year (April 1 to March 31). e.g. 2025-05-10 -> '2025-26'"""
        if d.month >= 4:
            return f"{d.year}-{str(d.year + 1)[-2:]}"
        else:
            return f"{d.year - 1}-{str(d.year)[-2:]}"

    def run_backtest(
        self,
        trades: List[TradeOrder],
        brokerage_pct: float = 0.0003,      # 3 bps (0.03%) or flat
        brokerage_cap_per_order: float = 20.0,
        exchange_rate: float = 0.0000345,   # NSE transaction charge 0.00345%
        sebi_rate: float = 0.000001         # SEBI turnover fee 0.0001% (₹10/crore)
    ) -> PortfolioBacktestResult:
        """
        Executes an institutional backtest processing trades chronologically by sell_date,
        tracking the ₹1.25 Lakh annual LTCG statutory exemption bucket across tax years.
        """
        sorted_trades = sorted(trades, key=lambda t: t.sell_date)

        # Track utilized LTCG exemption per tax year
        ltcg_utilized_by_year: Dict[str, float] = {}
        trade_reports: List[TradeExecutionReport] = []

        profitable_count = 0

        for t in sorted_trades:
            if t.sell_date <= t.buy_date:
                raise ValueError(f"Sell date {t.sell_date} must be strictly after buy date {t.buy_date}")

            slippage_frac = t.slippage_bps / 10000.0
            buy_price_eff = t.buy_price * (1.0 + slippage_frac)
            sell_price_eff = t.sell_price * (1.0 - slippage_frac)

            buy_turnover = round(buy_price_eff * t.quantity, 2)
            sell_turnover = round(sell_price_eff * t.quantity, 2)
            slippage_cost = round(((buy_price_eff - t.buy_price) + (t.sell_price - sell_price_eff)) * t.quantity, 2)

            gross_pnl = round(sell_turnover - buy_turnover, 2)

            # Transaction Charges:
            # 1. STT (0.1% buy + 0.1% sell delivery)
            stt_dict = self.tax_engine.calculate_stt_delivery(buy_turnover, sell_turnover)
            total_stt = stt_dict["total_stt"]

            # 2. Stamp Duty (0.015% buy only)
            stamp_duty = self.tax_engine.calculate_stamp_duty_delivery(buy_turnover)

            # 3. Brokerage (capped at ₹20 per leg or 0.03%)
            brok_buy = min(brokerage_cap_per_order, round(buy_turnover * brokerage_pct, 2))
            brok_sell = min(brokerage_cap_per_order, round(sell_turnover * brokerage_pct, 2))
            total_brokerage = round(brok_buy + brok_sell, 2)

            # 4. Exchange charges & SEBI fees
            exch_charges = round((buy_turnover + sell_turnover) * exchange_rate, 2)
            sebi_charges = round((buy_turnover + sell_turnover) * sebi_rate, 2)

            # 5. GST (18% on Brokerage + Exchange charges + SEBI charges)
            gst = self.tax_engine.calculate_gst(
                brokerage=total_brokerage,
                exchange_charges=exch_charges,
                sebi_fees=sebi_charges
            )

            total_friction = round(total_stt + stamp_duty + total_brokerage + exch_charges + sebi_charges + gst + slippage_cost, 2)
            net_pretax_pnl = round(gross_pnl - total_friction, 2)

            # 6. Taxes: Capital Gains
            ty = self._get_tax_year(t.sell_date)
            prior_ltcg = ltcg_utilized_by_year.get(ty, 0.0)

            tax_res = self.tax_engine.calculate_equity_capital_gains(
                buy_date=t.buy_date,
                buy_price=buy_price_eff,
                sell_date=t.sell_date,
                sell_price=sell_price_eff,
                quantity=t.quantity,
                cumulative_prior_ltcg_in_period=prior_ltcg
            )

            tax_payable = tax_res["tax_payable"]
            if tax_res["gain_type"] == "LTCG" and gross_pnl > 0:
                ltcg_utilized_by_year[ty] = prior_ltcg + tax_res["exemption_utilized"]

            net_posttax_pnl = round(net_pretax_pnl - tax_payable, 2)
            if net_posttax_pnl > 0:
                profitable_count += 1

            rep = TradeExecutionReport(
                isin=t.isin,
                ticker=t.ticker,
                buy_date=t.buy_date,
                sell_date=t.sell_date,
                quantity=t.quantity,
                buy_price_effective=round(buy_price_eff, 2),
                sell_price_effective=round(sell_price_eff, 2),
                buy_turnover=buy_turnover,
                sell_turnover=sell_turnover,
                gross_pnl=gross_pnl,
                stt_total=total_stt,
                stamp_duty=stamp_duty,
                brokerage_total=total_brokerage,
                exchange_charges=exch_charges,
                sebi_charges=sebi_charges,
                gst_total=gst,
                slippage_cost=slippage_cost,
                total_friction=total_friction,
                net_pretax_pnl=net_pretax_pnl,
                gain_type=tax_res["gain_type"],
                taxable_gain=tax_res["taxable_gain"],
                tax_rate=tax_res["tax_rate"],
                tax_payable=tax_payable,
                net_posttax_pnl=net_posttax_pnl
            )
            trade_reports.append(rep)

        n_trades = len(trade_reports)
        win_rate = round((profitable_count / n_trades) * 100.0, 2) if n_trades > 0 else 0.0

        return PortfolioBacktestResult(
            trades_count=n_trades,
            profitable_trades=profitable_count,
            win_rate_pct=win_rate,
            total_gross_pnl=round(sum(r.gross_pnl for r in trade_reports), 2),
            total_stt=round(sum(r.stt_total for r in trade_reports), 2),
            total_stamp_duty=round(sum(r.stamp_duty for r in trade_reports), 2),
            total_brokerage=round(sum(r.brokerage_total for r in trade_reports), 2),
            total_exchange_sebi_charges=round(sum(r.exchange_charges + r.sebi_charges for r in trade_reports), 2),
            total_gst=round(sum(r.gst_total for r in trade_reports), 2),
            total_slippage=round(sum(r.slippage_cost for r in trade_reports), 2),
            total_friction_costs=round(sum(r.total_friction for r in trade_reports), 2),
            net_pretax_pnl=round(sum(r.net_pretax_pnl for r in trade_reports), 2),
            total_tax_payable=round(sum(r.tax_payable for r in trade_reports), 2),
            net_posttax_pnl=round(sum(r.net_posttax_pnl for r in trade_reports), 2),
            trade_reports=trade_reports
        )
