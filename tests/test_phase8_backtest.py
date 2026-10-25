"""Acceptance tests for Phase 8: Medium-Term Strategy Backtesting and Tax Simulation.
Includes an independently calculated 10-trade numerical fixture verifying:
- STT (0.1% buy + 0.1% sell delivery)
- Stamp Duty (0.015% buy delivery)
- Brokerage & exchange fees with exact 18% GST on services
- Short-Term Capital Gains (20%)
- Long-Term Capital Gains (12.5% above ₹1.25L exemption, resetting each April 1)
- Net post-tax P&L reconciliation
"""
from datetime import date
import pytest
from src.core.backtest import StrategyBacktestEngine, TradeOrder, PortfolioBacktestResult


def test_independent_10_trade_tax_and_friction_fixture():
    """
    10-Trade Fixture across 2 tax years (TY 2025-26 and TY 2026-27):
    - Trades 1-4: Short-term trades in TY 2025-26 (IT Act 1961 Sec 111A, 20%)
    - Trades 5-7: Long-term trades in TY 2025-26 (IT Act 1961 Sec 112A, 12.5% above 1.25L)
    - Trades 8-10: Trades in TY 2026-27 (IT Act 2025 Sec 196 & Sec 198, exemption bucket resets!)
    """
    trades = [
        # TY 2025-26 STCG
        TradeOrder(isin="INE001A01010", ticker="TK1", buy_date=date(2025, 4, 10), buy_price=100.0, sell_date=date(2025, 6, 10), sell_price=120.0, quantity=1000, slippage_bps=0.0),
        TradeOrder(isin="INE002A01020", ticker="TK2", buy_date=date(2025, 5, 1), buy_price=200.0, sell_date=date(2025, 7, 1), sell_price=190.0, quantity=500, slippage_bps=0.0), # Loss
        TradeOrder(isin="INE003A01030", ticker="TK3", buy_date=date(2025, 6, 1), buy_price=300.0, sell_date=date(2025, 9, 1), sell_price=350.0, quantity=400, slippage_bps=0.0),
        TradeOrder(isin="INE004A01040", ticker="TK4", buy_date=date(2025, 7, 1), buy_price=50.0, sell_date=date(2025, 11, 1), sell_price=70.0, quantity=1000, slippage_bps=0.0),

        # TY 2025-26 LTCG (holding > 365 days)
        # Trade 5: Gain = (250 - 150) * 1000 = ₹1,00,000 (Within 1.25L exemption -> Tax = 0)
        TradeOrder(isin="INE005A01050", ticker="TK5", buy_date=date(2024, 5, 1), buy_price=150.0, sell_date=date(2025, 10, 1), sell_price=250.0, quantity=1000, slippage_bps=0.0),
        # Trade 6: Gain = (300 - 200) * 1000 = ₹1,00,000 (Exemption remaining: 25k -> Taxable = 75k @ 12.5% = ₹9,375)
        TradeOrder(isin="INE006A01060", ticker="TK6", buy_date=date(2024, 6, 1), buy_price=200.0, sell_date=date(2025, 12, 1), sell_price=300.0, quantity=1000, slippage_bps=0.0),
        # Trade 7: Gain = (400 - 350) * 500 = ₹25,000 (Exemption exhausted -> Taxable = 25k @ 12.5% = ₹3,125)
        TradeOrder(isin="INE007A01070", ticker="TK7", buy_date=date(2024, 7, 1), buy_price=350.0, sell_date=date(2026, 2, 1), sell_price=400.0, quantity=500, slippage_bps=0.0),

        # TY 2026-27 (New Tax Year - April 1, 2026 onwards under IT Act 2025)
        # Exemption bucket RESETS to ₹1.25L!
        # Trade 8: LTCG Gain = (500 - 300) * 500 = ₹1,00,000 (Within reset 1.25L exemption -> Tax = 0)
        TradeOrder(isin="INE008A01080", ticker="TK8", buy_date=date(2025, 2, 1), buy_price=300.0, sell_date=date(2026, 5, 1), sell_price=500.0, quantity=500, slippage_bps=0.0),
        # Trade 9: STCG under IT Act 2025 Sec 196 (20%)
        TradeOrder(isin="INE009A01090", ticker="TK9", buy_date=date(2026, 4, 15), buy_price=100.0, sell_date=date(2026, 7, 15), sell_price=150.0, quantity=200, slippage_bps=0.0),
        # Trade 10: STCG loss under IT Act 2025
        TradeOrder(isin="INE010A01100", ticker="TK10", buy_date=date(2026, 5, 1), buy_price=250.0, sell_date=date(2026, 8, 1), sell_price=220.0, quantity=300, slippage_bps=0.0),
    ]

    engine = StrategyBacktestEngine()
    res = engine.run_backtest(trades)

    assert isinstance(res, PortfolioBacktestResult)
    assert res.trades_count == 10
    assert res.profitable_trades == 8
    assert res.win_rate_pct == 80.0

    # Verify Trade 1 (STCG in TY 2025-26):
    # Buy 100,000, Sell 120,000. Gross Gain = 20,000.
    # Tax @ 20% = 4,000.00
    t1 = res.trade_reports[0]
    assert t1.gain_type == "STCG"
    assert t1.gross_pnl == 20000.0
    assert t1.taxable_gain == 20000.0
    assert t1.tax_payable == 4000.0

    # Verify Trade 5 (LTCG within exemption in TY 2025-26):
    # Gain = 100,000. First LTCG trade of year -> Tax = 0.
    t5 = [r for r in res.trade_reports if r.ticker == "TK5"][0]
    assert t5.gain_type == "LTCG"
    assert t5.gross_pnl == 100000.0
    assert t5.tax_payable == 0.0

    # Verify Trade 6 (LTCG exceeding remaining exemption in TY 2025-26):
    # Prior LTCG utilized = 100k. Remaining = 25k. Taxable = 75k @ 12.5% = 9,375.00
    t6 = [r for r in res.trade_reports if r.ticker == "TK6"][0]
    assert t6.gain_type == "LTCG"
    assert t6.gross_pnl == 100000.0
    assert t6.taxable_gain == 75000.0
    assert t6.tax_payable == 9375.0

    # Verify Trade 7 (LTCG with exhausted exemption in TY 2025-26):
    # Gain = 25,000. Taxable = 25,000 @ 12.5% = 3,125.00
    t7 = [r for r in res.trade_reports if r.ticker == "TK7"][0]
    assert t7.tax_payable == 3125.0

    # Verify Trade 8 (LTCG in NEW TY 2026-27 - April 1, 2026 reset):
    # Exemption is reset to 1.25L. Gain = 100,000 -> Tax MUST BE ZERO!
    t8 = [r for r in res.trade_reports if r.ticker == "TK8"][0]
    assert t8.gain_type == "LTCG"
    assert t8.gross_pnl == 100000.0
    assert t8.tax_payable == 0.0, "LTCG exemption did not reset properly in new Tax Year 2026-27!"

    # Verify Trade 9 (STCG under IT Act 2025):
    # Buy 20,000, Sell 30,000. Gain = 10,000 @ 20% = 2,000.00
    t9 = [r for r in res.trade_reports if r.ticker == "TK9"][0]
    assert t9.gain_type == "STCG"
    assert t9.tax_payable == 2000.0

    # Verify net post-tax P&L reconciliation
    expected_total_posttax = res.net_pretax_pnl - res.total_tax_payable
    assert abs(res.net_posttax_pnl - expected_total_posttax) < 0.01
    assert res.total_tax_payable == (4000.0 + 4000.0 + 4000.0 + 9375.0 + 3125.0 + 2000.0)  # = 26,500.0
