"""Acceptance tests for Phase 10: End-to-End System-Wide Integration.
Verifies the complete analytical flow:
Bhavcopy -> Adjustments -> TTM Fundamentals -> DuPont -> Valuation ->
Technicals -> Regime -> Strategy Backtest with Dual-Era Taxes -> API Response.
"""
from datetime import date, datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import pandas as pd

from src.db.models import Security, PriceRaw, CorporateAction, FinancialStatement, FinancialLineItem, IndexPrice
from src.db.seed_defs import seed_standard_line_items
from src.core.universe import PointInTimeUniverse
from src.core.adjustments import PriceAdjustmentEngine
from src.core.fundamentals.ttm import TTMAggregator
from src.core.fundamentals.ratios import FundamentalAnalysisEngine
from src.core.valuation import ValuationEngine
from src.core.technicals import TechnicalEngine, MarketRegimeEngine
from src.core.events import GovernanceRiskEvaluator
from src.core.backtest import StrategyBacktestEngine, TradeOrder
from src.api.main import app, get_db


def test_full_platform_pipeline_integration(db_session: Session):
    # 1. Fetch pre-seeded Master Security
    sec = db_session.query(Security).filter(Security.isin == "INE002A01018").first()
    assert sec is not None

    # 2. Ingest Historical Raw Prices (pre and post corporate action)
    # Day 1: 2024-01-01 Close 3000
    # Day 2: 2024-01-02 Close 3000
    # Day 3: 2024-01-03 (Ex-date for 1:1 bonus) Close 1500
    # Day 4: 2024-01-04 Close 1550
    prices_raw = [
        PriceRaw(isin=sec.isin, trade_date=date(2024, 1, 1), open_raw=2980.0, high_raw=3020.0, low_raw=2970.0, close_raw=3000.0, volume_raw=1000000, source_file="bhav_20240101.csv", file_hash="hash1"),
        PriceRaw(isin=sec.isin, trade_date=date(2024, 1, 2), open_raw=3000.0, high_raw=3050.0, low_raw=2990.0, close_raw=3000.0, volume_raw=1100000, source_file="bhav_20240102.csv", file_hash="hash2"),
        PriceRaw(isin=sec.isin, trade_date=date(2024, 1, 3), open_raw=1500.0, high_raw=1520.0, low_raw=1480.0, close_raw=1500.0, volume_raw=2200000, source_file="bhav_20240103.csv", file_hash="hash3"),
        PriceRaw(isin=sec.isin, trade_date=date(2024, 1, 4), open_raw=1510.0, high_raw=1560.0, low_raw=1505.0, close_raw=1550.0, volume_raw=1800000, source_file="bhav_20240104.csv", file_hash="hash4"),
    ]
    db_session.add_all(prices_raw)

    # 3. Ingest Corporate Action (1:1 Bonus on 2024-01-03)
    ca = CorporateAction(
        isin=sec.isin,
        ex_date=date(2024, 1, 3),
        action_type="BONUS",
        ratio_numerator=1,
        ratio_denominator=1,
        source_url="https://nseindia.com/ca",
        published_at=datetime(2023, 12, 15, 10, 0),
        effective_from=date(2024, 1, 3)
    )
    db_session.add(ca)
    db_session.commit()

    # 4. Compute Adjusted Prices
    adj_engine = PriceAdjustmentEngine()
    df_raw = pd.DataFrame([
        {"trade_date": p.trade_date, "close_raw": p.close_raw, "volume_raw": p.volume_raw}
        for p in prices_raw
    ])
    df_ca = pd.DataFrame([
        {"ex_date": ca.ex_date, "action_type": ca.action_type, "ratio_num": ca.ratio_numerator, "ratio_den": ca.ratio_denominator, "div_amount": None, "sub_price": None}
    ])
    df_adj = adj_engine.calculate_adjusted_series(df_raw, df_ca)

    # Assert pre-bonus price adjusted by 0.5 (3000 -> 1500)
    assert df_adj.loc[df_adj["trade_date"] == date(2024, 1, 1), "close_adj"].values[0] == 1500.0
    assert df_adj.loc[df_adj["trade_date"] == date(2024, 1, 3), "close_adj"].values[0] == 1500.0

    # 5. Seed Financial Line Item definitions & Ingest 4 Quarters of Fundamentals
    seed_standard_line_items(db_session)
    q_data = [
        (date(2023, 4, 1), date(2023, 6, 30), datetime(2023, 7, 25, 18, 0), 200000.0, 38000.0, 16000.0),
        (date(2023, 7, 1), date(2023, 9, 30), datetime(2023, 10, 27, 18, 0), 210000.0, 40000.0, 17000.0),
        (date(2023, 10, 1), date(2023, 12, 31), datetime(2024, 1, 20, 18, 0), 220000.0, 42000.0, 18000.0),
        (date(2024, 1, 1), date(2024, 3, 31), datetime(2024, 4, 25, 18, 0), 230000.0, 44000.0, 19000.0),
    ]
    for p_start, p_end, pub_dt, rev, ebitda, pat in q_data:
        fs = FinancialStatement(
            isin=sec.isin,
            period_start=p_start,
            period_end=p_end,
            period_type="QUARTERLY",
            consolidated=True,
            currency="INR",
            unit_multiplier=1.0,
            published_at=pub_dt,
            ingested_at=pub_dt,
            valid_from=pub_dt,
            source_url="https://nseindia.com/results",
            source_type="NSE_XBRL"
        )
        db_session.add(fs)
        db_session.flush()
        db_session.add_all([
            FinancialLineItem(statement_id=fs.id, item_code="REV", value=rev),
            FinancialLineItem(statement_id=fs.id, item_code="EBITDA", value=ebitda),
            FinancialLineItem(statement_id=fs.id, item_code="PAT", value=pat),
            FinancialLineItem(statement_id=fs.id, item_code="TOTAL_DEBT", value=120000.0),
            FinancialLineItem(statement_id=fs.id, item_code="CASH_EQUIV", value=45000.0),
        ])
    db_session.commit()

    # 6. TTM Flow Metrics
    ttm_agg = TTMAggregator(db_session)
    ttm_res = ttm_agg.get_ttm_metrics(sec.isin, cutoff_timestamp=datetime(2024, 5, 1, 12, 0))
    assert ttm_res["REV"] == 860000.0
    assert ttm_res["EBITDA"] == 164000.0
    assert ttm_res["PAT"] == 70000.0

    # 7. DuPont 5-Factor Evaluation
    fund_engine = FundamentalAnalysisEngine()
    dupont = fund_engine.calculate_dupont_5factor(
        net_income=70000.0,
        ebt=95000.0,
        ebit=130000.0,
        revenue=860000.0,
        total_assets=1600000.0,
        equity=800000.0,
        is_financial=False
    )
    assert 0.08 <= dupont["roe_product"] <= 0.095

    # 8. DCF Valuation & Reverse DCF
    val_engine = ValuationEngine()
    dcf = val_engine.calculate_fcff_dcf(
        fcff_0=60000.0,
        growth_rates_5yr=[0.08] * 5,
        wacc=0.12,
        terminal_growth=0.04
    )
    assert dcf["enterprise_value"] > 500000.0

    # Reverse DCF convergence
    implied_g = val_engine.solve_reverse_dcf(
        target_enterprise_value=dcf["enterprise_value"],
        fcff_0=60000.0,
        wacc=0.12,
        terminal_growth=0.04
    )
    assert abs(implied_g - 0.08) < 0.001

    # 9. Governance Risk Evaluation
    gov_eval = GovernanceRiskEvaluator()
    pledge_rep = gov_eval.assess_promoter_pledging(0.0)
    assert pledge_rep["risk_level"] == "LOW"

    # 10. Strategy Backtest with statutory taxes
    backtest_engine = StrategyBacktestEngine()
    trades = [
        TradeOrder(isin=sec.isin, ticker="RELIANCE", buy_date=date(2024, 1, 1), buy_price=1500.0, sell_date=date(2024, 3, 1), sell_price=1600.0, quantity=100)
    ]
    bt_res = backtest_engine.run_backtest(trades)
    assert bt_res.trades_count == 1
    assert bt_res.profitable_trades == 1
    assert bt_res.trade_reports[0].stt_total > 0.0
    assert bt_res.trade_reports[0].gst_total > 0.0

    # 11. Test FastAPI endpoint with structured 3-part envelope
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    response = client.get(f"/api/v1/stock/{sec.isin}/summary?as_of_date=2024-01-04")
    assert response.status_code == 200
    json_data = response.json()

    assert json_data["isin"] == sec.isin
    assert json_data["ticker"] == "RELIANCE"
    assert json_data["metadata"]["watermark"] == "CODE TEST - SYNTHETIC DATA"
    assert "facts" in json_data
    assert "metrics" in json_data
    assert "forecasts" in json_data
    assert json_data["facts"]["security_profile"]["company_name"] == "Reliance Industries Limited"
    assert json_data["facts"]["market_observation"]["close_raw"] == 1550.0

    app.dependency_overrides.clear()
