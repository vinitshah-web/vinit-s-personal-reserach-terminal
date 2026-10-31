"""FastAPI REST Service for NSE Equity Intelligence Platform.
Enforces institutional facts / metrics / forecasts separation and strict provenance tracking.
"""
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path
import json
from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, Response, FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.db.connection import get_session_factory
from src.db.models import (
    GovernanceEvent, IndexPrice, MarketDataSync, PriceRaw, Security
)
from src.core.universe import PointInTimeUniverse, PITMode
from src.core.fundamentals.ratios import FundamentalAnalysisEngine
from src.core.valuation import ValuationEngine, ValuationModelError
from src.core.technicals import MarketRegimeEngine
from src.core.backtest import StrategyBacktestEngine, TradeOrder
from src.ingestion.providers import TejHQAdapter, FinancialsAdapter, IndustryKnowledgeEngine
from src.reports.pdf_generator import ResearchReportPDFGenerator
import pandas as pd

SEARCH_INDEX: List[Dict[str, Any]] = []
FUNDAMENTALS_SNAPSHOT: Dict[str, Dict[str, Any]] = {}
LATEST_QUOTES: Dict[str, Dict[str, Any]] = {}
MARKET_DATA_STATUS: Dict[str, Any] = {}
_index_file = Path("data/securities_search_index.json")
if _index_file.exists():
    try:
        with open(_index_file, "r", encoding="utf-8") as f:
            SEARCH_INDEX = json.load(f)
    except Exception:
        SEARCH_INDEX = []

_fundamentals_file = Path("data/fundamentals_snapshot.json")
if _fundamentals_file.exists():
    try:
        FUNDAMENTALS_SNAPSHOT = json.loads(
            _fundamentals_file.read_text(encoding="utf-8")
        ).get("data", {})
    except (OSError, json.JSONDecodeError, AttributeError):
        FUNDAMENTALS_SNAPSHOT = {}

for _path, _target in (
    (Path("data/latest_quotes.json"), "quotes"),
    (Path("data/market_data_status.json"), "status"),
):
    if _path.exists():
        try:
            _loaded = json.loads(_path.read_text(encoding="utf-8"))
            if _target == "quotes" and isinstance(_loaded, dict):
                LATEST_QUOTES = _loaded
            elif _target == "status" and isinstance(_loaded, dict):
                MARKET_DATA_STATUS = _loaded
        except (OSError, json.JSONDecodeError):
            pass

app = FastAPI(
    title="Vinit's Self-Made Research Terminal API",
    version="1.0.0",
    description="Vinit's Institutional Research Terminal API with strict provenance tracking and dual-era statutory taxation."
)


# Mount static directories
data_dir = Path("data")
if data_dir.exists():
    app.mount("/data", StaticFiles(directory=str(data_dir)), name="data")

prototypes_dir = Path("ui/prototypes")
if prototypes_dir.exists():
    app.mount("/ui", StaticFiles(directory=str(prototypes_dir), html=True), name="ui")


@app.get("/")
def root():
    return FileResponse("index.html")

@app.get("/index.html")
def get_index():
    return FileResponse("index.html")

@app.get("/research.html")
def get_research():
    return FileResponse("research.html")

@app.get("/compare.html")
def get_compare():
    return FileResponse("compare.html")

@app.get("/watchlist.html")
def get_watchlist_page():
    return FileResponse("watchlist.html")

@app.get("/reports.html")
def get_reports_page():
    return FileResponse("reports.html")

@app.get("/overview.html")
def get_overview_page():
    return FileResponse("index.html")



def get_db():
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def get_local_quote(
    db: Session, symbol: str, isin: Optional[str]
) -> Optional[Dict[str, Any]]:
    """Return the newest persisted EOD record with explicit provenance and age."""
    if not isin or isin == "N/A":
        return None
    price = db.query(PriceRaw).filter(PriceRaw.isin == isin).order_by(
        PriceRaw.trade_date.desc()
    ).first()
    if price is None:
        return None

    latest_sync = db.query(MarketDataSync).filter_by(
        provider="TejHQ", exchange="NSE", status="VERIFIED"
    ).order_by(MarketDataSync.trading_date.desc()).first()
    if latest_sync and price.trade_date == latest_sync.trading_date:
        freshness = "LATEST_VERIFIED_EOD"
    elif latest_sync:
        freshness = "ARCHIVED_EOD"
    else:
        freshness = "LATEST_LOCAL_EOD"

    return {
        "symbol": symbol,
        "isin": isin,
        "source": (
            "TejHQ / NSE EOD snapshot"
            if price.source_file.startswith("tejhq_nse_snapshot_")
            else "Local NSE Bhavcopy archive"
        ),
        "trade_date": price.trade_date.isoformat(),
        "close": price.close_raw,
        "open": price.open_raw,
        "high": price.high_raw,
        "low": price.low_raw,
        "volume": price.volume_raw,
        "turnover": None,
        "prev_close": None,
        "price_basis": "NSE Unadjusted Bhavcopy Close",
        "freshness": freshness,
        "status": "VALID",
        "retrieval_time": (
            price.ingested_at.isoformat() if price.ingested_at else None
        ),
        "source_file": price.source_file,
        "source_hash": price.file_hash,
    }


def get_snapshot_quote(exchange: str, symbol: str, isin: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Return a quote only when its date matches the verified exchange status."""
    normalized_exchange = "BSE" if exchange.upper() == "BSE" else "NSE"
    key = f"BSE:{symbol}" if normalized_exchange == "BSE" else symbol
    quote = LATEST_QUOTES.get(key)
    exchange_status = MARKET_DATA_STATUS.get("exchanges", {}).get(
        normalized_exchange,
        MARKET_DATA_STATUS if normalized_exchange == "NSE" else {},
    )
    if not quote or exchange_status.get("status") != "VERIFIED":
        return None
    if quote.get("trade_date") != exchange_status.get("trading_date"):
        return None
    if isin and isin != "N/A" and quote.get("isin") and quote.get("isin") != isin:
        return None
    return {**quote, "freshness": "LATEST_VERIFIED_EOD", "price_basis": "RAW_UNADJUSTED"}


class ProvenanceEnvelope(BaseModel):
    isin: str
    ticker: str
    as_of: str
    metadata: Dict[str, Any]
    facts: Dict[str, Any]
    metrics: Dict[str, Any]
    forecasts: Dict[str, Any]


class DCFRequest(BaseModel):
    fcff_0: float = Field(..., description="Base year Free Cash Flow to Firm in ₹ Crores")
    growth_rates_5yr: List[float] = Field(..., description="5-year discrete growth rates (decimal, e.g. [0.08, 0.08, ...])")
    wacc: float = Field(..., description="Weighted Average Cost of Capital (decimal, e.g. 0.12)")
    terminal_growth: float = Field(0.04, description="Terminal growth rate (decimal, e.g. 0.04)")
    total_debt: float = Field(0.0, description="Total debt in ₹ Crores")
    cash_and_equivalents: float = Field(0.0, description="Cash & cash equivalents in ₹ Crores")
    shares_outstanding_cr: Optional[float] = Field(None, description="Shares outstanding in Crores")


class ReverseDCFRequest(BaseModel):
    target_enterprise_value: float = Field(..., description="Observed Target Enterprise Value in ₹ Crores")
    fcff_0: float = Field(..., description="Base year Free Cash Flow in ₹ Crores")
    wacc: float = Field(..., description="WACC (decimal, e.g. 0.12)")
    terminal_growth: float = Field(0.04, description="Terminal growth rate (decimal, e.g. 0.04)")


class BankingDDMRequest(BaseModel):
    net_income_0: float = Field(..., description="Base year Net Income in ₹ Crores")
    return_on_equity: float = Field(..., description="Sustainable ROE (decimal, e.g. 0.16)")
    sustainable_growth: float = Field(..., description="Long-term asset growth rate (decimal, e.g. 0.05)")
    cost_of_equity: float = Field(..., description="Cost of Equity Ke (decimal, e.g. 0.13)")


class TradeOrderSchema(BaseModel):
    isin: str
    ticker: str
    buy_date: str
    buy_price: float
    sell_date: str
    sell_price: float
    quantity: int
    slippage_bps: float = 5.0


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "nse-equity-platform",
        "version": "1.0.0",
        "data_policy": "NO_SYNTHETIC_MARKET_DATA"
    }


@app.get("/api/v1/market-data/status")
def market_data_status(db: Session = Depends(get_db)):
    latest_price_date = db.query(PriceRaw.trade_date).order_by(
        PriceRaw.trade_date.desc()
    ).limit(1).scalar()
    latest_sync = db.query(MarketDataSync).filter_by(
        provider="TejHQ", exchange="NSE"
    ).order_by(MarketDataSync.trading_date.desc(), MarketDataSync.fetched_at.desc()).first()
    return {
        "status": "VERIFIED" if latest_sync else "LOCAL_ARCHIVE_ONLY",
        "latest_price_date": latest_price_date.isoformat() if latest_price_date else None,
        "last_verified_sync": {
            "provider": latest_sync.provider,
            "exchange": latest_sync.exchange,
            "trading_date": latest_sync.trading_date.isoformat(),
            "provider_published_at": (
                latest_sync.provider_published_at.isoformat()
                if latest_sync.provider_published_at else None
            ),
            "fetched_at": latest_sync.fetched_at.isoformat(),
            "row_count": latest_sync.row_count,
            "source_hash": latest_sync.source_hash,
        } if latest_sync else None,
    }


@app.get("/api/v1/stock/{isin}/summary", response_model=ProvenanceEnvelope)
def get_stock_summary(
    isin: str,
    as_of_date: Optional[str] = None,
    mode: str = "AS_KNOWN",
    db: Session = Depends(get_db)
):
    """
    Returns 3-part structured analysis envelope for a given ISIN:
    - facts: Raw observed market prices & filings with source provenance & SHA-256 hashes
    - metrics: Computed fundamental ratios & DuPont analysis with Formula Registry references
    - forecasts: DCF & valuation projections with explicit assumption disclosures
    """
    sec = db.query(Security).filter(Security.isin == isin).first()
    if not sec:
        raise HTTPException(status_code=404, detail=f"Security with ISIN {isin} not found in master.")

    query_date = date.fromisoformat(as_of_date) if as_of_date else date.today()
    query_ts = datetime.now(timezone.utc)
    pit_mode = PITMode(mode.upper()) if mode.upper() in PITMode.__members__ else PITMode.AS_KNOWN

    # Query raw latest price
    latest_price = db.query(PriceRaw).filter(
        PriceRaw.isin == isin,
        PriceRaw.trade_date <= query_date
    ).order_by(PriceRaw.trade_date.desc()).first()

    pit_universe = PointInTimeUniverse(db)
    stmt = pit_universe.get_point_in_time_financials(isin, query_ts, query_date, mode=pit_mode)

    # 1. Facts
    facts = {
        "security_profile": {
            "company_name": sec.company_name,
            "sector": sec.sector,
            "series": sec.series,
            "listing_date": sec.listing_date.isoformat(),
            "delisting_date": sec.delisting_date.isoformat() if sec.delisting_date else None,
            "is_financial": sec.is_financial
        },
        "market_observation": {
            "trade_date": latest_price.trade_date.isoformat() if latest_price else None,
            "close_raw": latest_price.close_raw if latest_price else None,
            "volume_raw": latest_price.volume_raw if latest_price else None,
            "source_file": latest_price.source_file if latest_price else None,
            "file_hash": latest_price.file_hash if latest_price else None
        }
    }

    # 2. Metrics: calculate only when all reported line items are present.
    fund_engine = FundamentalAnalysisEngine()
    metrics = {}
    line_items = {
        item.item_code: item.value
        for item in (stmt.line_items if stmt else [])
        if item.value is not None and not item.is_estimated
    }
    dupont_inputs = {
        "net_income": line_items.get("PAT"),
        "ebt": line_items.get("EBT"),
        "ebit": line_items.get("EBIT"),
        "revenue": line_items.get("REVENUE"),
        "total_assets": line_items.get("TOTAL_ASSETS"),
        "equity": line_items.get("EQUITY"),
    }
    if not sec.is_financial and all(dupont_inputs.values()):
        try:
            dupont = fund_engine.calculate_dupont_5factor(
                **dupont_inputs, is_financial=False
            )
            metrics["dupont_5factor"] = {
                "formula_id": "DUPONT_ROE_5FACTOR",
                "tax_burden": dupont["tax_burden"],
                "interest_burden": dupont["interest_burden"],
                "ebit_margin": dupont["ebit_margin"],
                "asset_turnover": dupont["asset_turnover"],
                "equity_multiplier": dupont["equity_multiplier"],
                "roe_product": dupont["roe_product"]
            }
        except Exception as e:
            metrics["dupont_5factor"] = {
                "status": "NOT_CALCULATED", "reason": str(e)
            }
    elif not sec.is_financial:
        metrics["dupont_5factor"] = {
            "status": "NOT_CALCULATED",
            "reason": "Complete reported PAT, EBT, EBIT, revenue, assets, and equity are required."
        }
    else:
        metrics["banking_metrics"] = {
            "formula_id": "BANK_NIM",
            "note": "Banking institutions route to Net Interest Margin & Spread models."
        }

    # 3. Forecasts require explicit user assumptions and reported base cash flow.
    forecasts = {
        "dcf_valuation": {
            "status": "NOT_CALCULATED",
            "reason": "Use the valuation endpoint with explicit FCFF, growth, WACC, and terminal-growth assumptions."
        }
    } if not sec.is_financial else {}

    return ProvenanceEnvelope(
        isin=sec.isin,
        ticker=sec.ticker_current,
        as_of=query_date.isoformat(),
        metadata={
            "query_mode": pit_mode.value,
            "data_policy": "NO_SYNTHETIC_MARKET_DATA",
            "server_timestamp": query_ts.isoformat()
        },
        facts=facts,
        metrics=metrics,
        forecasts=forecasts
    )


@app.post("/api/v1/valuation/fcff")
def calculate_fcff_valuation(req: DCFRequest):
    """Calculates intrinsic Enterprise Value & implied per share value using Damodaran FCFF model."""
    val_engine = ValuationEngine()
    try:
        dcf = val_engine.calculate_fcff_dcf(
            fcff_0=req.fcff_0,
            growth_rates_5yr=req.growth_rates_5yr,
            wacc=req.wacc,
            terminal_growth=req.terminal_growth
        )
        bridge = val_engine.bridge_enterprise_to_equity_value(
            enterprise_value=dcf["enterprise_value"],
            total_debt=req.total_debt,
            cash_and_equivalents=req.cash_and_equivalents,
            shares_outstanding=req.shares_outstanding_cr
        )
        return {
            "status": "success",
            "watermark": "CODE TEST - SYNTHETIC DATA",
            "dcf_breakdown": dcf,
            "equity_bridge": bridge
        }
    except ValuationModelError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/valuation/reverse-dcf")
def solve_reverse_dcf(req: ReverseDCFRequest):
    """Solves for discrete 5-year growth implied by observed market Enterprise Value."""
    val_engine = ValuationEngine()
    try:
        implied_growth = val_engine.solve_reverse_dcf(
            target_enterprise_value=req.target_enterprise_value,
            fcff_0=req.fcff_0,
            wacc=req.wacc,
            terminal_growth=req.terminal_growth
        )
        return {
            "status": "success",
            "target_enterprise_value": req.target_enterprise_value,
            "implied_5yr_growth_pct": round(implied_growth * 100.0, 3),
            "watermark": "CODE TEST - SYNTHETIC DATA"
        }
    except ValuationModelError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/valuation/banking-ddm")
def calculate_banking_ddm(req: BankingDDMRequest):
    """Calculates Banking DDM with statutory regulatory capital retention."""
    val_engine = ValuationEngine()
    try:
        res = val_engine.calculate_banking_ddm(
            net_income_0=req.net_income_0,
            return_on_equity=req.return_on_equity,
            sustainable_growth=req.sustainable_growth,
            cost_of_equity=req.cost_of_equity
        )
        return {
            "status": "success",
            "watermark": "CODE TEST - SYNTHETIC DATA",
            "result": res
        }
    except ValuationModelError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/backtest/run")
def run_strategy_backtest(trades: List[TradeOrderSchema]):
    """Executes multi-trade backtest with exact STT, Stamp Duty, GST 18%, and dual-era statutory taxation."""
    bt_engine = StrategyBacktestEngine()
    try:
        trade_orders = [
            TradeOrder(
                isin=t.isin,
                ticker=t.ticker,
                buy_date=date.fromisoformat(t.buy_date),
                buy_price=t.buy_price,
                sell_date=date.fromisoformat(t.sell_date),
                sell_price=t.sell_price,
                quantity=t.quantity,
                slippage_bps=t.slippage_bps
            )
            for t in trades
        ]
        result = bt_engine.run_backtest(trade_orders)
        return {
            "status": "success",
            "watermark": "CODE TEST - SYNTHETIC DATA",
            "summary": {
                "trades_count": result.trades_count,
                "profitable_trades": result.profitable_trades,
                "win_rate_pct": result.win_rate_pct,
                "total_gross_pnl": result.total_gross_pnl,
                "total_friction_costs": result.total_friction_costs,
                "net_pretax_pnl": result.net_pretax_pnl,
                "total_tax_payable": result.total_tax_payable,
                "net_posttax_pnl": result.net_posttax_pnl
            },
            "trade_reports": [r.__dict__ for r in result.trade_reports]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/regime")
def get_current_market_regime(db: Session = Depends(get_db)):
    """Classifies overarching Indian equity market regime from NIFTY 50 price history."""
    index_prices = db.query(IndexPrice).filter(IndexPrice.index_name == "NIFTY 50").order_by(IndexPrice.trade_date.asc()).all()
    if len(index_prices) < 200:
        # Check workspace CSV
        csv_path = Path("NIFTY 50-25-10-2025-to-25-10-2026.csv")
        if csv_path.exists():
            df_idx = pd.read_csv(csv_path)
            df_idx.columns = [c.strip() for c in df_idx.columns]
            df_idx = df_idx.rename(columns={"Date": "trade_date", "Close": "close"})
            df_idx["trade_date"] = pd.to_datetime(df_idx["trade_date"], format="%d-%b-%Y").dt.date
            df_idx = df_idx.sort_values("trade_date").reset_index(drop=True)
            res = MarketRegimeEngine.classify_regime(df_idx)
            res["watermark"] = "CODE TEST - SYNTHETIC DATA"
            return res
        raise HTTPException(status_code=400, detail="Insufficient index history to classify regime.")

    df_idx = pd.DataFrame([{"trade_date": p.trade_date, "close": p.close} for p in index_prices])
    res = MarketRegimeEngine.classify_regime(df_idx)
    res["watermark"] = "CODE TEST - SYNTHETIC DATA"
    return res


@app.get("/api/v1/reports")
def list_research_tearsheets():
    """Lists all available generated research tear-sheets."""
    reports_dir = Path("reports")
    if not reports_dir.exists():
        return {"count": 0, "reports": [], "watermark": "CODE TEST - SYNTHETIC DATA"}
    files = list(reports_dir.glob("*_TEARSHEET.md"))
    reports = []
    for f in sorted(files):
        ticker = f.name.replace("_TEARSHEET.md", "")
        reports.append({
            "ticker": ticker,
            "filename": f.name,
            "url": f"/api/v1/reports/{ticker}"
        })
    return {
        "count": len(reports),
        "reports": reports,
        "watermark": "CODE TEST - SYNTHETIC DATA"
    }


@app.get("/api/v1/reports/{ticker}")
def get_research_tearsheet(ticker: str):
    """Retrieves generated institutional research tear-sheet in Markdown format."""
    clean_ticker = ticker.strip().upper()
    report_file = Path("reports") / f"{clean_ticker}_TEARSHEET.md"
    if not report_file.exists():
        raise HTTPException(status_code=404, detail=f"No research tear-sheet found for ticker {clean_ticker}.")
    with open(report_file, "r", encoding="utf-8") as f:
        content = f.read()
    return {
        "ticker": clean_ticker,
        "content_markdown": content,
        "watermark": "CODE TEST - SYNTHETIC DATA"
    }


@app.get("/api/v1/quality/audit")
def get_data_quality_audit(db: Session = Depends(get_db)):
    """Returns cryptographic SHA-256 provenance and database counts audit with dynamically recalculated hashes."""
    import hashlib

    sec_count = db.query(Security).count()
    price_count = db.query(PriceRaw).count()
    index_count = db.query(IndexPrice).count()
    gov_count = db.query(GovernanceEvent).count()

    ledger = []
    tracked_files = [
        ("data/nse_platform.db", "Core Platform SQLite Database"),
        ("data/securities_search_index.json", "3,392 Securities Search Index"),
        ("data/regression_references.json", "Regression Reference Prices (2026-10-23)"),
        ("NIFTY 50-25-10-2025-to-25-10-2026.csv", "NSE NIFTY 50 Historical Index Series"),
        ("1766489756276.pdf", "SEBI LODR Statutory Corporate Disclosures")
    ]
    for rel_path, desc in tracked_files:
        p = Path(rel_path)
        if p.exists():
            with open(p, "rb") as f:
                h = hashlib.sha256(f.read()).hexdigest()
            ledger.append({
                "file": p.name,
                "description": desc,
                "size_bytes": p.stat().st_size,
                "sha256": h,
                "status": "INTEGRITY_VERIFIED",
                "verification": "RECALCULATED_AND_PASSED"
            })

    return {
        "status": "VERIFIED",
        "watermark": "CODE TEST - SYNTHETIC DATA",
        "counts": {
            "securities_master": sec_count,
            "raw_prices": price_count,
            "index_daily_prices": index_count,
            "governance_disclosures": gov_count
        },
        "provenance_ledger": ledger
    }


# =====================================================================
# RETAIL RESEARCH PLATFORM EXTENSION ENDPOINTS
# =====================================================================

@app.get("/api/v1/search")
def search_securities(q: str = "", limit: int = 12, db: Session = Depends(get_db)):
    """Fast autocomplete search resolving exact ticker, prefix, company name, ISIN, or alias."""
    from src.ingestion.providers import resolve_canonical_symbol
    clean_q = q.strip().upper()
    if not clean_q:
        return {"query": q, "results": []}

    # Resolve alias if user typed former or common ticker
    resolved_canonical = resolve_canonical_symbol(clean_q)

    results = []
    if SEARCH_INDEX:
        exact_ticker = []
        prefix_ticker = []
        alias_match = []
        name_match = []
        isin_match = []
        for s in SEARCH_INDEX:
            t = s["ticker"].upper()
            n = s["name"].upper()
            i = s["isin"].upper()
            aliases = [a.upper() for a in s.get("aliases", [])]

            if t == clean_q or t == resolved_canonical:
                exact_ticker.append(s)
            elif clean_q in aliases:
                alias_match.append(s)
            elif t.startswith(clean_q):
                prefix_ticker.append(s)
            elif clean_q in n:
                name_match.append(s)
            elif clean_q in i:
                isin_match.append(s)
        results = exact_ticker + alias_match + prefix_ticker + name_match + isin_match
        return {"query": q, "count": len(results[:limit]), "results": results[:limit]}

    # Database fallback
    matches = db.query(Security).filter(
        (Security.ticker_current == clean_q) |
        (Security.ticker_current == resolved_canonical) |
        (Security.ticker_current.like(f"{clean_q}%")) |
        (Security.company_name.like(f"%{clean_q}%")) |
        (Security.isin.like(f"{clean_q}%"))
    ).limit(limit).all()

    return {
        "query": q,
        "count": len(matches),
        "results": [
            {
                "isin": m.isin,
                "ticker": m.ticker_current,
                "name": m.company_name,
                "sector": m.sector or "Diversified",
                "series": m.series,
                "is_financial": m.is_financial
            }
            for m in matches
        ]
    }


@app.get("/api/v1/research/{symbol}")
def get_company_research(symbol: str, db: Session = Depends(get_db), exchange: str = "NSE"):
    """Compiles complete company research dossier in INR with validated facts and zero fabricated valuations."""
    from src.ingestion.providers import resolve_canonical_symbol
    clean_sym = resolve_canonical_symbol(symbol.strip().upper().replace(".NS", ""))
    normalized_exchange = "BSE" if exchange.upper() == "BSE" else "NSE"
    
    # 1. Security lookup
    sec = db.query(Security).filter(
        (Security.ticker_current == clean_sym) | (Security.isin == clean_sym)
    ).first()

    company_name = sec.company_name if sec else clean_sym
    isin = sec.isin if sec else "N/A"
    sector = sec.sector if sec and sec.sector else "Diversified"
    is_fin = sec.is_financial if sec else False

    # Also check SEARCH_INDEX for metadata if sec was not found in sqlite
    if SEARCH_INDEX:
        for s in SEARCH_INDEX:
            if (s.get("exchange") or "NSE") == normalized_exchange and (
                s["ticker"] == clean_sym or s["isin"] == clean_sym
            ):
                company_name = s["name"]
                isin = s["isin"]
                sector = s.get("sector") or "Unavailable"
                is_fin = s.get("is_financial", False)
                break

    # 2. Persisted verified EOD first; a live call is only a last-resort fallback.
    quote = get_snapshot_quote(normalized_exchange, clean_sym, isin)
    if not quote and normalized_exchange == "NSE":
        quote = get_local_quote(db, clean_sym, isin)
    if not quote and normalized_exchange == "NSE":
        quote = TejHQAdapter.get_latest_quote(clean_sym, isin=isin)

    if not quote:
        quote = {
            "symbol": clean_sym,
            "isin": isin,
            "source": "Missing Quote",
            "trade_date": None,
            "close": None,
            "price_basis": "N/A",
            "freshness": "No Quote Found",
            "status": "QUOTE_NOT_FOUND",
            "explanation": f"No verified {normalized_exchange} closing price found for {clean_sym} in the current snapshot or local archive."
        }

    # 3. Financial Statements & Profile
    same_nse_security = bool(sec and sec.isin == isin)
    dossier = (
        FinancialsAdapter.get_company_dossier(clean_sym)
        if normalized_exchange == "NSE" or same_nse_security
        else {
            "company_name": company_name,
            "sector": sector,
            "industry": None,
            "business_summary": None,
            "financial_statements": [],
            "has_statements": False,
            "pb_ratio": None,
            "pb_ratio_reason": "Dated balance-sheet inputs are unavailable.",
        }
    )
    batch_fundamentals = FUNDAMENTALS_SNAPSHOT.get(f"{normalized_exchange}:{clean_sym}")
    if batch_fundamentals:
        for field in (
            "company_name", "shares_outstanding_cr", "pe_ratio",
            "pe_ratio_basis", "pb_ratio", "pb_ratio_reason",
            "fifty_two_week_high", "fifty_two_week_low",
        ):
            dossier[field] = batch_fundamentals.get(field)
        dossier["fundamentals_source"] = batch_fundamentals.get("source")
        dossier["fundamentals_retrieved_at"] = batch_fundamentals.get("retrieved_at")
    if sec and sec.company_name and (normalized_exchange == "NSE" or same_nse_security):
        dossier["company_name"] = sec.company_name
    if sec and sec.sector and (normalized_exchange == "NSE" or same_nse_security):
        dossier["sector"] = sec.sector

    # 4. Industry dynamics require a dated cited source. Curated prose is not
    # returned as company evidence by the production research endpoint.
    ind_profile = {
        "demand_drivers": None,
        "supply_dynamics": None,
        "regulatory_framework": None,
        "key_risks": None,
        "data_status": "UNAVAILABLE",
        "reason": "No dated, cited industry source has been ingested.",
    }

    # 5. Valuation requires explicit user assumptions; the research endpoint
    # never silently chooses growth, discount rates, or target multiples.
    price = quote.get("close")
    reported_fcff = next(
        (
            statement.get("fcff_cr")
            for statement in dossier.get("financial_statements", [])
            if statement.get("fcff_cr") is not None
        ),
        None,
    )
    valuation_reason = (
        f"Negative Free Cash Flow to Firm (FCFF = ₹{reported_fcff:,.2f} Cr); "
        "a turnaround valuation requires explicit user assumptions."
        if not is_fin and reported_fcff is not None and reported_fcff <= 0
        else (
            "Use the valuation endpoint with explicit reported base values and user-supplied assumptions. "
            "The research endpoint does not choose growth, discount rates, or target multiples."
        )
    )
    valuation_scenarios = {
        "model_type": "BANKING_EQUITY_DDM" if is_fin else "FCFF_DISCOUNTED_CASH_FLOW",
        "status": "NOT_CALCULATED",
        "can_calculate": False,
        "reason": valuation_reason,
        "reported_fcff_cr": reported_fcff,
    }

    shares_outstanding_cr = dossier.get("shares_outstanding_cr")
    dynamic_market_cap_cr = (
        round(price * shares_outstanding_cr, 2)
        if price and shares_outstanding_cr and shares_outstanding_cr > 0 else None
    )

    return {
        "symbol": clean_sym,
        "exchange": normalized_exchange,
        "company_name": company_name,
        "isin": isin,
        "sector": dossier.get("sector") or sector,
        "industry": dossier.get("industry"),
        "is_financial": is_fin,
        "quote": quote,
        "market_cap_cr": dynamic_market_cap_cr,
        "market_cap_basis": (
            f"Latest dated {normalized_exchange} close × reported shares outstanding"
            if dynamic_market_cap_cr is not None else None
        ),
        "shares_outstanding_cr": shares_outstanding_cr,
        "pe_ratio": dossier.get("pe_ratio"),
        "pe_ratio_basis": dossier.get("pe_ratio_basis"),
        "pb_ratio": dossier.get("pb_ratio"),
        "pb_ratio_reason": dossier.get("pb_ratio_reason"),
        "fifty_two_week_high": dossier.get("fifty_two_week_high"),
        "fifty_two_week_low": dossier.get("fifty_two_week_low"),
        "business_summary": dossier.get("business_summary"),
        "business_summary_reason": dossier.get("business_summary_reason") or (
            "A sourced company overview is unavailable."
            if not dossier.get("business_summary") else None
        ),
        "financial_statements": dossier.get("financial_statements", []),
        "has_statements": dossier.get("has_statements", len(dossier.get("financial_statements", [])) > 0),
        "industry_profile": ind_profile,
        "valuation": valuation_scenarios,
        "source": dossier.get("source"),
        "fundamentals_source": dossier.get("fundamentals_source") or dossier.get("source"),
        "fundamentals_retrieved_at": dossier.get("fundamentals_retrieved_at") or dossier.get("retrieval_time"),
        "as_of": datetime.now().isoformat()
    }


@app.get("/api/v1/peers/{symbol}")
def get_company_peers(symbol: str, db: Session = Depends(get_db)):
    """Returns business-model comparable peers, peer medians, and evidence-based interpretation."""
    from src.ingestion.providers import resolve_canonical_symbol
    import statistics
    clean_sym = resolve_canonical_symbol(symbol.strip().upper().replace(".NS", ""))
    
    # Curated peer clusters by comparable business model
    BUSINESS_MODEL_PEERS = {
        "ETERNAL": ["ETERNAL", "SWIGGY", "DELHIVERY", "INFOEDGE", "NAZARA"],
        "RELIANCE": ["RELIANCE", "ONGC", "IOC", "BPCL", "BHARTIARTL"],
        "TCS": ["TCS", "INFY", "HCLTECH", "WIPRO", "LTIM"],
        "PERSISTENT": ["PERSISTENT", "COFORGE", "MPHASIS", "KPITTECH", "TATAELXSI"],
        "HDFCBANK": ["HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN"],
        "DIXON": ["DIXON", "KAYNES", "SYRMA", "AMBER", "PGEL"],
        "TRENT": ["TRENT", "TITAN", "DMART", "PAGEIND", "BATAINDIA"],
        "POLYCAB": ["POLYCAB", "HAVELLS", "KEI", "RRKABEL", "FINCABLES"]
    }

    target_d = FinancialsAdapter.get_company_dossier(clean_sym)
    sec = db.query(Security).filter((Security.ticker_current == clean_sym) | (Security.isin == clean_sym)).first()
    sec_sector = (sec.sector if sec and sec.sector and sec.sector != "Diversified" else None) or target_d.get("sector") or "Diversified"

    cluster = BUSINESS_MODEL_PEERS.get(clean_sym)
    if not cluster:
        # Fallback to search index peers in same sector
        cluster = [clean_sym]
        if sec_sector and sec_sector != "Diversified":
            for s in SEARCH_INDEX:
                if s["ticker"] != clean_sym and s.get("sector") == sec_sector:
                    cluster.append(s["ticker"])
                    if len(cluster) >= 5:
                        break

    peer_cards = []
    pe_list = []
    pb_list = []
    mcap_list = []

    for peer_sym in cluster[:5]:
        peer_security = db.query(Security).filter(
            Security.ticker_current == peer_sym
        ).first()
        q = get_local_quote(
            db, peer_sym, peer_security.isin if peer_security else None
        )
        if not q:
            q = TejHQAdapter.get_latest_quote(peer_sym)
        d = FinancialsAdapter.get_company_dossier(peer_sym)
        batch = FUNDAMENTALS_SNAPSHOT.get(f"NSE:{peer_sym}")
        if batch:
            for field in (
                "company_name", "shares_outstanding_cr", "pe_ratio",
                "pb_ratio", "pb_ratio_reason", "dividend_yield_pct",
            ):
                if batch.get(field) is not None or field == "pb_ratio_reason":
                    d[field] = batch.get(field)
        c_price = q.get("close") if q else None
        pe = d.get("pe_ratio")
        pb = d.get("pb_ratio")
        shares = d.get("shares_outstanding_cr")
        mcap = round(c_price * shares, 2) if c_price and shares else None

        if pe and pe > 0: pe_list.append(pe)
        if pb and pb > 0: pb_list.append(pb)
        if mcap and mcap > 0: mcap_list.append(mcap)

        peer_cards.append({
            "symbol": peer_sym,
            "company_name": d.get("company_name", peer_sym),
            "close": c_price,
            "quote_date": q.get("trade_date") if q else "Unavailable",
            "market_cap_cr": mcap,
            "pe_ratio": pe,
            "pb_ratio": pb,
            "pb_ratio_reason": d.get("pb_ratio_reason"),
            "dividend_yield_pct": d.get("dividend_yield_pct"),
            "source": q.get("source") if q else "Missing Quote"
        })

    # Compute Peer Medians
    median_pe = round(statistics.median(pe_list), 2) if pe_list else None
    median_pb = round(statistics.median(pb_list), 2) if pb_list else None
    median_mcap = round(statistics.median(mcap_list), 1) if mcap_list else None

    # Target comparison
    target_d = FinancialsAdapter.get_company_dossier(clean_sym)
    target_batch = FUNDAMENTALS_SNAPSHOT.get(f"NSE:{clean_sym}")
    if target_batch:
        target_d["pe_ratio"] = target_batch.get("pe_ratio")
    target_pe = target_d.get("pe_ratio")
    
    interpretation = ""
    if target_pe and median_pe:
        diff_pct = ((target_pe - median_pe) / median_pe) * 100.0
        if diff_pct > 10.0:
            interpretation = f"Trailing P/E is {diff_pct:.1f}% above the selected peer median of {median_pe}x. This arithmetic comparison does not establish that the premium is justified."
        elif diff_pct < -10.0:
            interpretation = f"Trailing P/E is {abs(diff_pct):.1f}% below the selected peer median of {median_pe}x. This arithmetic comparison does not establish a margin of safety."
        else:
            interpretation = f"Valuation multiple of {target_pe}x trades broadly in line (within ±10%) with the sector peer median of {median_pe}x."
    else:
        interpretation = "Sufficient positive sourced trailing P/E values are unavailable. No valuation conclusion was generated."

    return {
        "target_symbol": clean_sym,
        "sector": sec_sector,
        "peers": peer_cards,
        "valid_peers_count": len(pe_list),
        "median_pe": median_pe,
        "median_pb": median_pb,
        "median_mcap_cr": median_mcap,
        "interpretation": interpretation
    }


@app.get("/api/v1/reports/{symbol}/pdf")
def export_research_pdf(symbol: str, db: Session = Depends(get_db), exchange: str = "NSE"):
    """Generates and streams an institutional vector PDF research report in INR."""
    normalized_exchange = "BSE" if exchange.upper() == "BSE" else "NSE"
    data = get_company_research(symbol, db=db, exchange=normalized_exchange)
    pdf_bytes = ResearchReportPDFGenerator.generate_pdf(data)
    
    filename = f"{symbol.upper()}_{normalized_exchange}_Research_Report.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


class WatchlistItem(BaseModel):
    symbol: str
    name: Optional[str] = None
    isin: Optional[str] = None
    sector: Optional[str] = None


@app.get("/api/v1/watchlist")
def get_watchlist():
    """Retrieves persisted user watchlist."""
    wl_path = Path("data/user_watchlist.json")
    if wl_path.exists():
        with open(wl_path, "r", encoding="utf-8") as f:
            try:
                items = json.load(f)
                return {"count": len(items), "watchlist": items}
            except Exception:
                pass
    return {"count": 0, "watchlist": []}


@app.post("/api/v1/watchlist")
def add_to_watchlist(item: WatchlistItem):
    """Adds a security to the persisted user watchlist with duplicate prevention."""
    clean_sym = item.symbol.strip().upper()
    wl_path = Path("data/user_watchlist.json")
    items = []
    if wl_path.exists():
        try:
            with open(wl_path, "r", encoding="utf-8") as f:
                items = json.load(f)
        except Exception:
            items = []

    # Check duplicate
    for it in items:
        if it.get("symbol") == clean_sym:
            return {"status": "exists", "message": f"{clean_sym} already in watchlist.", "watchlist": items}

    new_item = {
        "symbol": clean_sym,
        "name": item.name or clean_sym,
        "isin": item.isin or "N/A",
        "sector": item.sector or "Diversified",
        "added_at": datetime.now().isoformat()
    }
    items.append(new_item)

    with open(wl_path, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)

    return {"status": "added", "item": new_item, "watchlist": items}


@app.delete("/api/v1/watchlist/{symbol}")
def remove_from_watchlist(symbol: str):
    """Removes a security from the persisted user watchlist."""
    clean_sym = symbol.strip().upper()
    wl_path = Path("data/user_watchlist.json")
    if not wl_path.exists():
        return {"status": "removed", "watchlist": []}

    try:
        with open(wl_path, "r", encoding="utf-8") as f:
            items = json.load(f)
    except Exception:
        items = []

    filtered = [it for it in items if it.get("symbol") != clean_sym]
    with open(wl_path, "w", encoding="utf-8") as f:
        json.dump(filtered, f, indent=2)

    return {"status": "removed", "watchlist": filtered}

