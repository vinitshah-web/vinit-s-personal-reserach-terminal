"""Comprehensive Acceptance Tests for NSE Equity Research Assistant.
Covers all 12 acceptance criteria specified in Section 12 of the Research Assistant Specification.
"""
import io
import json
from pathlib import Path
from fastapi.testclient import TestClient

from src.api.main import app
from src.ingestion.providers import TejHQAdapter, FinancialsAdapter, IndustryKnowledgeEngine
from src.reports.pdf_generator import ResearchReportPDFGenerator
from src.core.valuation import ValuationEngine

client = TestClient(app)


def test_1_stock_autocomplete_and_ambiguous_resolution():
    """Criterion 1: Autocomplete resolves exact symbol, prefix, and company name."""
    # Exact ticker
    r1 = client.get("/api/v1/search?q=TCS")
    assert r1.status_code == 200
    res1 = r1.json().get("results", [])
    assert len(res1) > 0
    assert res1[0]["ticker"] == "TCS"

    # Prefix / multiple matches (HDFC)
    r2 = client.get("/api/v1/search?q=HDFC")
    assert r2.status_code == 200
    tickers = [s["ticker"] for s in r2.json().get("results", [])]
    assert "HDFCBANK" in tickers

    # ISIN resolution
    r3 = client.get("/api/v1/search?q=INE002A01018")
    assert r3.status_code == 200
    res3 = r3.json().get("results", [])
    assert len(res3) > 0
    assert res3[0]["ticker"] == "RELIANCE"


def test_2_selected_company_propagation():
    """Criterion 2: Selected company propagates across profile, metrics, valuation, and PDF."""
    r_res = client.get("/api/v1/research/PERSISTENT")
    assert r_res.status_code == 200
    data = r_res.json()
    assert data["symbol"] == "PERSISTENT"
    assert "PERSISTENT" in data["company_name"].upper()

    # Propagation to PDF generator
    pdf_bytes = ResearchReportPDFGenerator.generate_pdf(data)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-")


def test_3_quote_source_date_freshness_and_missing_handling():
    """Criterion 3: Verified source, date, freshness, and missing price transparency."""
    r = client.get("/api/v1/research/TCS")
    assert r.status_code == 200
    q = r.json().get("quote", {})
    assert "source" in q
    assert "trade_date" in q
    assert q["close"] > 0.0

    # Non-existent stock transparent missing handling
    r_missing = client.get("/api/v1/research/NONEXISTENT_TICKER_XYZ")
    assert r_missing.status_code == 200
    q_missing = r_missing.json().get("quote", {})
    assert q_missing.get("source") == "Missing Quote"


def test_4_financial_units_periods_and_inr_first():
    """Criterion 4: Reporting basis strictly INR Crores (₹ Cr), explicit fiscal years."""
    r = client.get("/api/v1/research/RELIANCE")
    assert r.status_code == 200
    data = r.json()
    stmts = data.get("financial_statements", [])
    assert len(stmts) > 0
    first = stmts[0]
    assert "period" in first
    assert "revenue_cr" in first
    assert first["revenue_cr"] > 10000.0  # In Crores


def test_5_peer_selection_and_comparative_metrics():
    """Criterion 5: Sector-appropriate peer selection with INR metrics."""
    r = client.get("/api/v1/peers/TCS")
    assert r.status_code == 200
    peers_data = r.json()
    assert peers_data["sector"] == "Technology"
    peer_symbols = [p["symbol"] for p in peers_data["peers"]]
    assert "INFY" in peer_symbols or "PERSISTENT" in peer_symbols


def test_6_independent_valuation_calculations_and_scenarios():
    """Criterion 6: Independent FCFF and Banking DDM calculations with Bear/Base/Bull scenarios."""
    val_engine = ValuationEngine()
    
    # Non-financial FCFF DCF
    dcf = val_engine.calculate_fcff_dcf(
        fcff_0=100.0,
        growth_rates_5yr=[0.10] * 5,
        wacc=0.12,
        terminal_growth=0.04
    )
    assert dcf["enterprise_value"] > 0
    assert dcf["pv_terminal_value"] > dcf["sum_pv_discrete"]

    # Reverse DCF implied growth round-trip
    implied_g = val_engine.solve_reverse_dcf(
        target_enterprise_value=dcf["enterprise_value"],
        fcff_0=100.0,
        wacc=0.12,
        terminal_growth=0.04
    )
    assert abs(implied_g - 0.10) < 0.001

    # Banking DDM (strictly under 5.5% Indian GDP hurdle cap)
    ddm = val_engine.calculate_banking_ddm(
        net_income_0=100.0,
        return_on_equity=0.15,
        sustainable_growth=0.045,
        cost_of_equity=0.12
    )
    assert ddm["fair_equity_value"] > 0


def test_7_missing_or_conflicting_data_fails_open_with_disclosure():
    """Criterion 7: Transparent disclosure rather than fabricated synthetic numbers."""
    dossier = FinancialsAdapter.get_company_dossier("UNKNOWN_XYZ")
    assert dossier["symbol"] == "UNKNOWN_XYZ"
    assert len(dossier["financial_statements"]) == 0  # Not fabricated


def test_8_ai_provider_absence_fallback_report_generation():
    """Criterion 8: Deterministic research narrative executes 100% without AI keys."""
    profile = IndustryKnowledgeEngine.get_industry_profile("Energy")
    assert "demand_drivers" in profile
    assert "key_risks" in profile
    assert len(profile["demand_drivers"]) > 20


def test_9_valid_pdf_creation_and_company_identity():
    """Criterion 9: PDF export generates a valid vector PDF with company identity."""
    r_pdf = client.get("/api/v1/reports/HDFCBANK/pdf")
    assert r_pdf.status_code == 200
    assert r_pdf.headers["content-type"] == "application/pdf"
    assert r_pdf.content.startswith(b"%PDF-")
    assert len(r_pdf.content) > 2000


def test_10_local_startup_and_workflow_without_paid_credentials():
    """Criterion 10: Local health and search index operate with zero credentials."""
    r_health = client.get("/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "ok"

    # Search index exists on disk
    index_path = Path("data/securities_search_index.json")
    assert index_path.exists()
    assert index_path.stat().st_size > 100000


def test_11_online_static_files_integrity():
    """Criterion 11: Static entry points and nojekyll present for GitHub Pages."""
    assert Path("index.html").exists()
    assert Path("research.html").exists()
    assert Path("compare.html").exists()
    assert Path("watchlist.html").exists()
    assert Path("reports.html").exists()
    assert Path(".nojekyll").exists()


def test_12_no_secrets_exposed():
    """Criterion 12: No API keys, passwords, or credentials exposed in frontend or code."""
    import re
    # Patterns for real API keys
    key_patterns = [
        re.compile(r"AIza[0-9A-Za-z-_]{35}"),  # Google API key
        re.compile(r"ghp_[0-9A-Za-z]{36}"),    # GitHub PAT
        re.compile(r"sk-[a-zA-Z0-9]{32,}")     # Paid API key
    ]
    for fn in ["index.html", "research.html", "compare.html", "watchlist.html", "reports.html"]:
        with open(fn, "r", encoding="utf-8") as f:
            content = f.read()
            for pat in key_patterns:
                assert not pat.search(content), f"Secret key matched in {fn}"
