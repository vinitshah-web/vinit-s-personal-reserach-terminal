"""Extended API endpoint tests for Valuation, Backtest, Regime and Report endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from src.api.main import app, get_db


def test_api_health():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["watermark"] == "CODE TEST - SYNTHETIC DATA"


def test_api_valuation_fcff():
    client = TestClient(app)
    payload = {
        "fcff_0": 60.0,
        "growth_rates_5yr": [0.08, 0.08, 0.08, 0.08, 0.08],
        "wacc": 0.12,
        "terminal_growth": 0.04,
        "total_debt": 100.0,
        "cash_and_equivalents": 20.0,
        "shares_outstanding_cr": 10.0
    }
    resp = client.post("/api/v1/valuation/fcff", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert abs(data["dcf_breakdown"]["enterprise_value"] - 919.6616) < 0.01
    assert data["equity_bridge"]["total_debt"] == 100.0
    assert data["equity_bridge"]["cash_and_equivalents"] == 20.0
    assert data["equity_bridge"]["implied_per_share"] > 0


def test_api_valuation_reverse_dcf():
    client = TestClient(app)
    payload = {
        "target_enterprise_value": 919.6616,
        "fcff_0": 60.0,
        "wacc": 0.12,
        "terminal_growth": 0.04
    }
    resp = client.post("/api/v1/valuation/reverse-dcf", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert abs(data["implied_5yr_growth_pct"] - 8.0) < 0.05


def test_api_valuation_banking_ddm():
    client = TestClient(app)
    payload = {
        "net_income_0": 5000.0,
        "return_on_equity": 0.16,
        "sustainable_growth": 0.05,
        "cost_of_equity": 0.13
    }
    resp = client.post("/api/v1/valuation/banking-ddm", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["result"]["retention_ratio"] == 0.3125
    assert data["result"]["payout_ratio"] == 0.6875


def test_api_backtest_run():
    client = TestClient(app)
    payload = [
        {
            "isin": "INE002A01018",
            "ticker": "RELIANCE",
            "buy_date": "2025-05-01",
            "buy_price": 2500.0,
            "sell_date": "2025-06-01",
            "sell_price": 2700.0,
            "quantity": 100,
            "slippage_bps": 0.0
        }
    ]
    resp = client.post("/api/v1/backtest/run", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["summary"]["trades_count"] == 1
    assert data["summary"]["profitable_trades"] == 1
    assert data["summary"]["total_gross_pnl"] == 20000.0
    assert data["summary"]["total_tax_payable"] == 4000.0  # 20% STCG under Sec 111A


def test_api_get_research_tearsheet():
    client = TestClient(app)
    resp = client.get("/api/v1/reports/RELIANCE")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "RELIANCE"
    assert "INSTITUTIONAL EQUITY RESEARCH TEARSHEET" in data["content_markdown"]
    assert "CODE TEST — SYNTHETIC DATA" in data["content_markdown"]


def test_api_list_research_tearsheets():
    client = TestClient(app)
    resp = client.get("/api/v1/reports")
    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data
    assert data["count"] >= 15
    tickers = [r["ticker"] for r in data["reports"]]
    assert "RELIANCE" in tickers
    assert "TCS" in tickers
    assert "HDFCBANK" in tickers


def test_api_data_quality_audit(db_session: Session):
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.get("/api/v1/quality/audit")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "VERIFIED"
    assert "counts" in data
    assert "provenance_ledger" in data
    assert len(data["provenance_ledger"]) >= 3
    app.dependency_overrides.clear()


def test_api_market_regime(db_session: Session):
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.get("/api/v1/regime")
    assert resp.status_code == 200
    data = resp.json()
    assert "regime" in data
    assert "realized_vol_20d_pct" in data
    assert data["watermark"] == "CODE TEST - SYNTHETIC DATA"
    app.dependency_overrides.clear()
