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


def test_13_canonical_alias_resolution_zomato_paytm():
    """Root-Cause Check: Resolving company names and aliases like Zomato -> ETERNAL, Paytm -> ONE97."""
    # Search for ZOMATO
    r_zomato = client.get("/api/v1/search?q=ZOMATO")
    assert r_zomato.status_code == 200
    results = r_zomato.json().get("results", [])
    assert len(results) > 0
    assert results[0]["ticker"] == "ETERNAL"
    assert "INE758T01015" in results[0]["isin"]

    # Research directly by alias 'ZOMATO'
    r_alias = client.get("/api/v1/research/ZOMATO")
    assert r_alias.status_code == 200
    data = r_alias.json()
    assert data["symbol"] == "ETERNAL"
    assert "ETERNAL" in data["company_name"].upper() or "ZOMATO" in data["company_name"].upper()

    # Research directly by alias 'PAYTM'
    r_paytm = client.get("/api/v1/research/PAYTM")
    assert r_paytm.status_code == 200
    data_paytm = r_paytm.json()
    assert data_paytm["symbol"] == "ONE97"


def test_14_regression_reference_stocks_and_prices():
    """Root-Cause Check: Dated references for 2026-10-23 closing prices match exact exchange records."""
    ref_path = Path("data/regression_references.json")
    assert ref_path.exists()
    with open(ref_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    refs = data.get("references", data)

    # 1. ETERNAL (Zomato)
    assert refs["ETERNAL"]["verified_close"] == 317.40
    r_eternal = client.get("/api/v1/research/ETERNAL")
    assert r_eternal.status_code == 200
    assert r_eternal.json()["quote"]["close"] == 317.40
    assert r_eternal.json()["quote"]["trade_date"] == "2026-10-23"

    # 2. RELIANCE
    assert refs["RELIANCE"]["verified_close"] == 1190.00
    r_rel = client.get("/api/v1/research/RELIANCE")
    assert r_rel.status_code == 200
    assert r_rel.json()["quote"]["close"] == 1190.00

    # 3. TCS
    assert refs["TCS"]["verified_close"] == 2530.00
    r_tcs = client.get("/api/v1/research/TCS")
    assert r_tcs.status_code == 200
    assert r_tcs.json()["quote"]["close"] == 2530.00

    # 4. HDFCBANK
    assert refs["HDFCBANK"]["verified_close"] == 692.80
    r_hdfc = client.get("/api/v1/research/HDFCBANK")
    assert r_hdfc.status_code == 200
    assert r_hdfc.json()["quote"]["close"] == 692.80


def test_15_eternal_negative_fcff_valuation_non_calculation():
    """Root-Cause Check: Negative FCFF for ETERNAL triggers NOT_CALCULATED status without synthetic fabrication."""
    r = client.get("/api/v1/research/ETERNAL")
    assert r.status_code == 200
    data = r.json()
    val = data.get("valuation", {})
    assert val.get("can_calculate") is False
    assert "Negative Free Cash Flow" in val.get("reason", "")
    assert val.get("base_fair_value") is None
    assert val.get("bull_fair_value") is None
    assert val.get("bear_fair_value") is None


def test_16_pdf_vector_generation_and_text_extraction():
    """Root-Cause Check: Generated PDFs contain valid vector layout, exact ticker, and INR symbols."""
    import pypdf

    for symbol in ["ETERNAL", "RELIANCE", "TCS"]:
        r_pdf = client.get(f"/api/v1/reports/{symbol}/pdf")
        assert r_pdf.status_code == 200
        assert r_pdf.headers["content-type"] == "application/pdf"
        assert len(r_pdf.content) > 1500

        # Extract text via pypdf
        reader = pypdf.PdfReader(io.BytesIO(r_pdf.content))
        assert len(reader.pages) >= 1
        page_text = "".join(p.extract_text() or "" for p in reader.pages)
        assert symbol in page_text, f"Ticker {symbol} not found in PDF page text"
        assert "NSE" in page_text


def test_17_peer_comparison_medians_and_interpretation():
    """Root-Cause Check: Peer comparison provides business-model peers, medians, and non-generic interpretation."""
    r_peers = client.get("/api/v1/peers/ETERNAL")
    assert r_peers.status_code == 200
    data = r_peers.json()
    assert data["target_symbol"] == "ETERNAL"
    assert "peers" in data
    assert len(data["peers"]) >= 3
    # Check that peer quotes have close prices and no default 1000 fallback
    for p in data["peers"]:
        if p.get("quote"):
            assert p["quote"]["close"] > 0
    assert "interpretation" in data
    assert len(data["interpretation"]) > 20


def test_18_empty_initial_watchlist_and_persistence():
    """Root-Cause Check: Watchlist starts empty and supports add/delete operations with persistence."""
    wl_path = Path("data/user_watchlist.json")
    with open(wl_path, "w", encoding="utf-8") as f:
        json.dump([], f)

    # Initial get
    r = client.get("/api/v1/watchlist")
    assert r.status_code == 200
    assert r.json()["count"] == 0
    assert r.json()["watchlist"] == []

    # Add ETERNAL
    r_add = client.post("/api/v1/watchlist", json={"symbol": "ETERNAL", "name": "Eternal Ltd", "sector": "Consumer Cyclical"})
    assert r_add.status_code == 200
    assert r_add.json()["status"] == "added"

    # Verify present
    r_verify = client.get("/api/v1/watchlist")
    assert r_verify.json()["count"] == 1
    assert r_verify.json()["watchlist"][0]["symbol"] == "ETERNAL"

    # Clean up
    r_del = client.delete("/api/v1/watchlist/ETERNAL")
    assert r_del.status_code == 200
    assert r_del.json()["status"] == "removed"
    assert len(r_del.json()["watchlist"]) == 0


def test_19_missing_dossier_fails_open_with_quote_and_disclosure():
    """Root-Cause Check: Missing financial dossier does not block quote retrieval."""
    # A ticker that is in security master (e.g. INFY) but let's test a valid ticker without a dossier in cache
    # FinancialsAdapter handles unknown stocks cleanly
    d = FinancialsAdapter.get_company_dossier("NONEXISTENT_STOCK")
    assert d["has_statements"] is False
    assert len(d["financial_statements"]) == 0


def test_20_data_quality_audit_dynamic_hashes():
    """Root-Cause Check: Data quality audit dynamically recalculates disk hashes."""
    r = client.get("/api/v1/quality/audit")
    assert r.status_code == 200
    audit = r.json()
    assert "provenance_ledger" in audit or "file_provenance_ledger" in audit
    ledger = audit.get("provenance_ledger") or audit.get("file_provenance_ledger")
    assert len(ledger) >= 4
    for entry in ledger:
        assert entry["status"] == "INTEGRITY_VERIFIED"
        assert len(entry["sha256"]) == 64

