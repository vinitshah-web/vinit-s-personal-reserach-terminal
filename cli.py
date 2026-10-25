"""Institutional Analyst Command Line Interface for NSE Equity Intelligence Platform.
Enables rapid terminal research, DCF valuation, Reverse DCF solving, backtesting, and tear-sheet display.
"""
import argparse
import sys
from datetime import date
from pathlib import Path

# Configure utf-8 stdout on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.db.connection import get_session_factory
from src.db.models import Security, PriceRaw, IndexPrice
from src.core.valuation import ValuationEngine
from src.core.technicals import MarketRegimeEngine
from src.core.backtest import StrategyBacktestEngine, TradeOrder
from src.core.forecasting import ForecastingEngine
from src.reports.generator import ResearchReportGenerator
from scripts.generate_demo_reports import DEMO_UNIVERSE
import pandas as pd


def cmd_summary(args):
    session_factory = get_session_factory()
    session = session_factory()
    try:
        sec = session.query(Security).filter(Security.isin == args.isin).first()
        if not sec:
            print(f"[ERROR] Security with ISIN {args.isin} not found.")
            return

        latest_price = session.query(PriceRaw).filter(PriceRaw.isin == args.isin).order_by(PriceRaw.trade_date.desc()).first()
        print(f"\n========================================================")
        print(f"  NSE EQUITY INTELLIGENCE TERMINAL — SECURITY SUMMARY")
        print(f"  WATERMARK: CODE TEST — SYNTHETIC DATA")
        print(f"========================================================")
        print(f"  Company Name : {sec.company_name}")
        print(f"  Ticker       : {sec.ticker_current}")
        print(f"  ISIN         : {sec.isin}")
        print(f"  Series       : {sec.series}")
        print(f"  Financial?   : {'YES (Bank/NBFC)' if sec.is_financial else 'NO'}")
        if latest_price:
            print(f"  Latest Close : ₹{latest_price.close_raw:,.2f} ({latest_price.trade_date})")
            print(f"  Traded Volume: {latest_price.volume_raw:,}")
            print(f"  Source File  : {latest_price.source_file}")
            print(f"  SHA-256 Hash : {latest_price.file_hash[:16]}...")
        print(f"========================================================\n")
    finally:
        session.close()


def cmd_dcf(args):
    val = ValuationEngine()
    rates = [args.growth] * 5
    res = val.calculate_fcff_dcf(
        fcff_0=args.fcff,
        growth_rates_5yr=rates,
        wacc=args.wacc,
        terminal_growth=args.terminal
    )
    bridge = val.bridge_enterprise_to_equity_value(
        enterprise_value=res["enterprise_value"],
        total_debt=args.debt,
        cash_and_equivalents=args.cash,
        shares_outstanding=args.shares
    )
    print(f"\n--- DAMODARAN FCFF VALUATION ---")
    print(f"  Base FCFF           : ₹{args.fcff:,.2f} Cr")
    print(f"  Discrete 5-Yr Growth: {args.growth:.1%}")
    print(f"  WACC                : {args.wacc:.1%}")
    print(f"  Terminal Growth     : {args.terminal:.1%}")
    print(f"  -------------------------------")
    print(f"  Discrete PV Sum     : ₹{res['sum_pv_discrete']:,.2f} Cr")
    print(f"  PV of Terminal Val  : ₹{res['pv_terminal_value']:,.2f} Cr")
    print(f"  Enterprise Value    : ₹{res['enterprise_value']:,.2f} Cr")
    print(f"  Equity Value        : ₹{bridge['equity_value']:,.2f} Cr")
    if bridge["implied_per_share"]:
        print(f"  Implied Per Share   : ₹{bridge['implied_per_share']:,.2f}")
    print(f"--------------------------------\n")


def cmd_reverse_dcf(args):
    val = ValuationEngine()
    implied_g = val.solve_reverse_dcf(
        target_enterprise_value=args.ev,
        fcff_0=args.fcff,
        wacc=args.wacc,
        terminal_growth=args.terminal
    )
    print(f"\n--- REVERSE DCF IMPLIED GROWTH SOLVER ---")
    print(f"  Target Enterprise Value: ₹{args.ev:,.2f} Cr")
    print(f"  Base Year FCFF         : ₹{args.fcff:,.2f} Cr")
    print(f"  Assumed WACC           : {args.wacc:.1%}")
    print(f"  Assumed Terminal Growth: {args.terminal:.1%}")
    print(f"  ----------------------------------------")
    print(f"  Market-Implied 5-Yr FCFF CAGR: {implied_g:.2%}")
    print(f"----------------------------------------\n")


def cmd_banking_ddm(args):
    val = ValuationEngine()
    res = val.calculate_banking_ddm(
        net_income_0=args.ni,
        return_on_equity=args.roe,
        sustainable_growth=args.growth,
        cost_of_equity=args.ke
    )
    print(f"\n--- BANKING REGULATORY CAPITAL DDM ---")
    print(f"  Net Income (Base)   : ₹{args.ni:,.2f} Cr")
    print(f"  Return on Equity    : {args.roe:.1%}")
    print(f"  Asset Growth Rate   : {args.growth:.1%}")
    print(f"  Cost of Equity (Ke) : {args.ke:.1%}")
    print(f"  -------------------------------------")
    print(f"  Retention Ratio (b) : {res['retention_ratio']:.2%}")
    print(f"  Payout Ratio (1-b)  : {res['payout_ratio']:.2%}")
    print(f"  Expected Dividend D1: ₹{res['expected_dividend_1']:,.2f} Cr")
    print(f"  Fair Equity Value   : ₹{res['fair_equity_value']:,.2f} Cr")
    print(f"-------------------------------------\n")


def cmd_regime(args):
    csv_path = Path("NIFTY 50-25-10-2025-to-25-10-2026.csv")
    if not csv_path.exists():
        print("[ERROR] Nifty 50 historical CSV not found.")
        return
    df_idx = pd.read_csv(csv_path)
    df_idx.columns = [c.strip() for c in df_idx.columns]
    df_idx = df_idx.rename(columns={"Date": "trade_date", "Close": "close"})
    df_idx["trade_date"] = pd.to_datetime(df_idx["trade_date"], format="%d-%b-%Y").dt.date
    df_idx = df_idx.sort_values("trade_date").reset_index(drop=True)
    res = MarketRegimeEngine.classify_regime(df_idx)

    print(f"\n--- INDIAN EQUITY MARKET REGIME ---")
    print(f"  As-Of Date           : {res['as_of_date']}")
    print(f"  Nifty 50 Close       : ₹{res['index_close']:,.2f}")
    print(f"  200-Day SMA          : ₹{res['index_dma200']:,.2f}")
    print(f"  Trend Direction      : {res['trend']}")
    print(f"  20-Day Realized Vol  : {res['realized_vol_20d_pct']:.2f}% (Annualized)")
    print(f"  Active Market Regime : {res['regime']}")
    print(f"-----------------------------------\n")


def cmd_tearsheet(args):
    ticker = args.ticker.upper().strip()
    match = [d for d in DEMO_UNIVERSE if d["ticker"] == ticker]
    if match:
        content = ResearchReportGenerator.generate_markdown_tearsheet(match[0])
        print(content)
    else:
        print(f"[ERROR] No pre-compiled tear-sheet for ticker {ticker}.")


def main():
    parser = argparse.ArgumentParser(description="NSE Equity Intelligence Institutional Analyst CLI")
    subparsers = parser.add_subparsers(dest="command")

    # summary
    p_sum = subparsers.add_parser("summary", help="Stock master & latest price summary")
    p_sum.add_argument("isin", help="12-character ISIN (e.g. INE002A01018)")
    p_sum.set_defaults(func=cmd_summary)

    # dcf
    p_dcf = subparsers.add_parser("dcf", help="Damodaran FCFF DCF model")
    p_dcf.add_argument("--fcff", type=float, default=60.0, help="Base FCFF in Cr")
    p_dcf.add_argument("--growth", type=float, default=0.08, help="5-yr discrete growth (e.g. 0.08)")
    p_dcf.add_argument("--wacc", type=float, default=0.12, help="WACC (e.g. 0.12)")
    p_dcf.add_argument("--terminal", type=float, default=0.04, help="Terminal growth (e.g. 0.04)")
    p_dcf.add_argument("--debt", type=float, default=0.0, help="Total debt in Cr")
    p_dcf.add_argument("--cash", type=float, default=0.0, help="Cash in Cr")
    p_dcf.add_argument("--shares", type=float, default=None, help="Shares in Cr")
    p_dcf.set_defaults(func=cmd_dcf)

    # reverse-dcf
    p_rdcf = subparsers.add_parser("reverse-dcf", help="Reverse DCF implied growth solver")
    p_rdcf.add_argument("--ev", type=float, required=True, help="Observed Enterprise Value in Cr")
    p_rdcf.add_argument("--fcff", type=float, default=60.0, help="Base FCFF in Cr")
    p_rdcf.add_argument("--wacc", type=float, default=0.12, help="WACC")
    p_rdcf.add_argument("--terminal", type=float, default=0.04, help="Terminal growth")
    p_rdcf.set_defaults(func=cmd_reverse_dcf)

    # banking-ddm
    p_ddm = subparsers.add_parser("banking-ddm", help="Banking DDM model")
    p_ddm.add_argument("--ni", type=float, required=True, help="Base Net Income in Cr")
    p_ddm.add_argument("--roe", type=float, default=0.16, help="ROE (e.g. 0.16)")
    p_ddm.add_argument("--growth", type=float, default=0.05, help="Asset growth")
    p_ddm.add_argument("--ke", type=float, default=0.13, help="Cost of Equity Ke")
    p_ddm.set_defaults(func=cmd_banking_ddm)

    # regime
    p_reg = subparsers.add_parser("regime", help="Market regime analysis")
    p_reg.set_defaults(func=cmd_regime)

    # tearsheet
    p_tear = subparsers.add_parser("tearsheet", help="Display research tearsheet")
    p_tear.add_argument("ticker", help="NSE ticker symbol (e.g. RELIANCE, TCS, INFY)")
    p_tear.set_defaults(func=cmd_tearsheet)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
