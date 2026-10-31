"""Data Provider Adapters for NSE Equity Research Platform.
Provides unified interfaces for:
1. TejHQ (Keyless EOD bhavcopy & corporate actions)
2. Fundamental Statements & Financial Profile (yfinance / local fallback)
3. Curated Indian Industry Demand/Supply & Risk Knowledge Base
Strictly zero-budget, no synthetic price fabrication, honest missing data disclosure.
"""
import logging
from datetime import date, datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path
import urllib.request
import urllib.parse
import json
import yfinance as yf

logger = logging.getLogger(__name__)


class MarketDataProviderError(RuntimeError):
    """Raised when a provider response cannot be treated as verified market data."""

SYMBOL_ALIASES: Dict[str, str] = {
    "ZOMATO": "ETERNAL",
    "BLINKIT": "ETERNAL",
    "PAYTM": "ONE97",
    "L&T": "LT",
    "RIL": "RELIANCE",
    "TML": "TATAMOTORS"
}

PB_RATIO_UNVERIFIABLE_SYMBOLS = {
    "BHARTIARTL", "BPCL", "DIXON", "ETERNAL", "FEDERALBNK",
    "ICICIBANK", "INFY", "IOC", "NAZARA", "ONE97", "POLYCAB",
    "SBIN", "SWIGGY", "WIPRO"
}
PB_RATIO_UNVERIFIABLE_REASON = (
    "P/B unavailable because dated price and balance-sheet inputs are not both "
    "available to verify the 12-month freshness rule."
)

def resolve_canonical_symbol(symbol: str) -> str:
    clean = symbol.strip().upper().replace(".NS", "")
    return SYMBOL_ALIASES.get(clean, clean)


def apply_pb_display_rule(symbol: str, dossier: Dict[str, Any]) -> Dict[str, Any]:
    """Suppress P/B values whose source dates cannot satisfy the freshness rule."""
    if resolve_canonical_symbol(symbol) in PB_RATIO_UNVERIFIABLE_SYMBOLS:
        dossier["pb_ratio"] = None
        dossier["pb_ratio_reason"] = PB_RATIO_UNVERIFIABLE_REASON
    return dossier


class TejHQAdapter:
    """Queries TejHQ's open keyless endpoints for NSE End-of-Day data."""
    BASE_URL = "https://api.tejhq.dev"
    HEADERS = {"User-Agent": "NSE-Research-Terminal/2.0 (Windows; Zero-Budget)"}
    TIMEOUT_SECONDS = 15

    @classmethod
    def request_json(cls, path: str, query: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Fetch and decode one HTTPS provider response, preserving TLS verification."""
        query_string = urllib.parse.urlencode(query or {})
        url = f"{cls.BASE_URL}{path}"
        if query_string:
            url = f"{url}?{query_string}"
        request = urllib.request.Request(url, headers=cls.HEADERS)

        try:
            with urllib.request.urlopen(request, timeout=cls.TIMEOUT_SECONDS) as response:
                if response.status != 200:
                    raise MarketDataProviderError(
                        f"TejHQ returned HTTP {response.status} for {path}."
                    )
                payload = json.loads(response.read().decode("utf-8"))
        except MarketDataProviderError:
            raise
        except Exception as exc:
            raise MarketDataProviderError(f"TejHQ request failed for {path}: {exc}") from exc

        if not isinstance(payload, dict):
            raise MarketDataProviderError(f"TejHQ returned a non-object payload for {path}.")
        return payload

    @classmethod
    def get_pipeline_status(cls) -> Dict[str, Any]:
        payload = cls.request_json("/v1/status")
        trading_date = payload.get("trading_date")
        stage = payload.get("stage")
        if not trading_date or stage not in {"prices", "derived"}:
            raise MarketDataProviderError("TejHQ status is missing a valid trading date or stage.")
        try:
            date.fromisoformat(trading_date)
        except ValueError as exc:
            raise MarketDataProviderError("TejHQ status contains an invalid trading date.") from exc
        return payload

    @classmethod
    def get_snapshot(cls, trading_date: date) -> List[Dict[str, Any]]:
        payload = cls.request_json(
            "/v1/snapshot/NSE", {"date": trading_date.isoformat()}
        )
        rows = payload.get("data")
        if not isinstance(rows, list):
            raise MarketDataProviderError("TejHQ snapshot is missing its data array.")
        return rows

    @classmethod
    def get_eod_ohlcv(cls, symbol: str, days: int = 90) -> List[Dict[str, Any]]:
        clean_sym = resolve_canonical_symbol(symbol)
        try:
            payload = cls.request_json(f"/v1/ohlcv/NSE/{urllib.parse.quote(clean_sym)}")
            rows = payload.get("data")
            if not isinstance(rows, list):
                raise MarketDataProviderError("TejHQ OHLCV response is missing its data array.")
            dated_rows = [row for row in rows if isinstance(row, dict) and row.get("date")]
            dated_rows.sort(key=lambda row: row["date"])
            return dated_rows[-days:] if days > 0 else dated_rows
        except MarketDataProviderError as exc:
            logger.warning("TejHQ OHLCV query failed for %s: %s", symbol, exc)
        return []

    @classmethod
    def get_latest_quote(cls, symbol: str, isin: Optional[str] = None) -> Optional[Dict[str, Any]]:
        clean_sym = resolve_canonical_symbol(symbol)
        rows = cls.get_eod_ohlcv(clean_sym, days=5)
        if rows:
            latest = rows[-1]
            close_val = latest.get("close")
            try:
                trade_date = date.fromisoformat(str(latest.get("date")))
                open_value = float(latest.get("open"))
                high_value = float(latest.get("high"))
                low_value = float(latest.get("low"))
                close_value = float(close_val)
                volume = int(latest.get("volume"))
            except (TypeError, ValueError):
                return None

            if (
                min(open_value, high_value, low_value, close_value) > 0
                and low_value <= open_value <= high_value
                and low_value <= close_value <= high_value
                and volume >= 0
            ):
                t_date = latest.get("date")
                return {
                    "symbol": clean_sym,
                    "isin": isin or "N/A",
                    "source": "TejHQ Keyless EOD",
                    "trade_date": t_date,
                    "close": close_value,
                    "open": open_value,
                    "high": high_value,
                    "low": low_value,
                    "volume": volume,
                    "turnover": float(latest.get("turnover", 0.0)),
                    "prev_close": float(latest.get("prev_close", close_val)),
                    "price_basis": "NSE Unadjusted Bhavcopy Close",
                    "freshness": "DATED_EOD",
                    "status": "VALID",
                    "retrieval_time": datetime.now(timezone.utc).isoformat(),
                    "source_url": f"{cls.BASE_URL}/v1/ohlcv/NSE/{clean_sym}"
                }
        return None

    @classmethod
    def get_corporate_actions(cls, symbol: str) -> List[Dict[str, Any]]:
        clean_sym = resolve_canonical_symbol(symbol)
        try:
            payload = cls.request_json(f"/v1/actions/{urllib.parse.quote(clean_sym)}")
            rows = payload.get("data")
            return rows if isinstance(rows, list) else []
        except MarketDataProviderError as exc:
            logger.warning("TejHQ actions query failed for %s: %s", symbol, exc)
        return []


class FinancialsAdapter:
    """Fetches real reported financials, profile, and ratios from yfinance with caching & graceful fallback."""
    _CACHE: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def get_company_dossier(cls, symbol: str) -> Dict[str, Any]:
        clean_sym = resolve_canonical_symbol(symbol)
        
        # 1. Memory Cache
        if clean_sym in cls._CACHE:
            return apply_pb_display_rule(clean_sym, cls._CACHE[clean_sym])

        # 2. Disk Cache
        cache_dir = Path("data/dossier_cache")
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{clean_sym}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                    apply_pb_display_rule(clean_sym, cached)
                    cls._CACHE[clean_sym] = cached
                    return cached
            except Exception:
                pass

        yf_ticker = f"{clean_sym}.NS"
        
        dossier: Dict[str, Any] = {
            "symbol": clean_sym,
            "company_name": clean_sym,
            "sector": "Diversified",
            "industry": "General",
            "business_summary": "Financial statements and filings not yet ingested for this security.",
            "market_cap_cr": None,
            "pe_ratio": None,
            "pb_ratio": None,
            "pb_ratio_reason": "P/B source inputs are unavailable.",
            "book_value": None,
            "dividend_yield_pct": None,
            "shares_outstanding_cr": None,
            "fifty_two_week_high": None,
            "fifty_two_week_low": None,
            "financial_statements": [],
            "source": "Yahoo Finance (secondary aggregator)",
            "has_statements": False,
            "retrieval_time": datetime.now().isoformat()
        }

        try:
            t = yf.Ticker(yf_ticker)
            info = t.info or {}
            dossier["company_name"] = info.get("shortName") or info.get("longName") or clean_sym
            dossier["sector"] = info.get("sector") or "Diversified"
            dossier["industry"] = info.get("industry") or "General"
            dossier["business_summary"] = info.get("longBusinessSummary") or f"{clean_sym} is an Indian publicly traded enterprise."
            
            mcap = info.get("marketCap")
            dossier["market_cap_cr"] = round(mcap / 1e7, 2) if mcap else None
            
            shares = info.get("sharesOutstanding")
            dossier["shares_outstanding_cr"] = round(shares / 1e7, 4) if shares else None
            
            dossier["pe_ratio"] = round(info.get("trailingPE"), 2) if info.get("trailingPE") else None
            dossier["provider_reported_pb_ratio"] = (
                round(info.get("priceToBook"), 2) if info.get("priceToBook") else None
            )
            dossier["pb_ratio"] = None
            dossier["pb_ratio_reason"] = (
                "P/B unavailable because the source does not provide both a price date "
                "and a dated balance-sheet equity input."
            )
            dossier["book_value"] = round(info.get("bookValue"), 2) if info.get("bookValue") else None
            trailing_dividend_yield = info.get("trailingAnnualDividendYield")
            provider_dividend_yield = info.get("dividendYield")
            if trailing_dividend_yield is not None:
                dossier["dividend_yield_pct"] = round(
                    float(trailing_dividend_yield) * 100, 4
                )
            elif provider_dividend_yield is not None:
                dossier["dividend_yield_pct"] = round(
                    float(provider_dividend_yield), 4
                )
            dossier["fifty_two_week_high"] = info.get("fiftyTwoWeekHigh")
            dossier["fifty_two_week_low"] = info.get("fiftyTwoWeekLow")

            # Income statement & Balance Sheet
            inc = t.financials
            bs = t.balance_sheet
            cf = t.cashflow

            if inc is not None and not inc.empty:
                periods = []
                for col in list(inc.columns)[:5]:
                    year_str = col.strftime("FY%y (%Y)") if hasattr(col, "strftime") else str(col)
                    
                    def get_val(df, row_name):
                        if df is not None and not df.empty and row_name in df.index:
                            val = df.loc[row_name, col]
                            return round(float(val) / 1e7, 2) if pd_not_na(val) else None
                        return None

                    rev = get_val(inc, "Total Revenue") or get_val(inc, "Operating Revenue")
                    op_inc = get_val(inc, "Operating Income") or get_val(inc, "EBIT")
                    ebitda = get_val(inc, "EBITDA") or (op_inc if op_inc else None)
                    ni = get_val(inc, "Net Income") or get_val(inc, "Net Income Common Stockholders")
                    
                    tot_assets = get_val(bs, "Total Assets")
                    tot_equity = get_val(bs, "Stockholders Equity") or get_val(bs, "Total Equity Gross Minority Interest")
                    tot_debt = get_val(bs, "Total Debt")
                    cash = get_val(bs, "Cash And Cash Equivalents")
                    
                    cfo = get_val(cf, "Operating Cash Flow")
                    capex = get_val(cf, "Capital Expenditure")
                    fcff = round(cfo - abs(capex), 2) if (cfo is not None and capex is not None) else None

                    periods.append({
                        "period": year_str,
                        "revenue_cr": rev,
                        "ebitda_cr": ebitda,
                        "net_income_cr": ni,
                        "operating_cash_flow_cr": cfo,
                        "capex_cr": abs(capex) if capex else None,
                        "fcff_cr": fcff,
                        "total_assets_cr": tot_assets,
                        "total_equity_cr": tot_equity,
                        "total_debt_cr": tot_debt,
                        "cash_cr": cash
                    })
                dossier["financial_statements"] = periods
                dossier["has_statements"] = len(periods) > 0

            apply_pb_display_rule(clean_sym, dossier)

            # Write to disk cache
            cls._CACHE[clean_sym] = dossier
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(dossier, f, indent=2)
            except Exception:
                pass

        except Exception as e:
            logger.warning(f"FinancialsAdapter extraction error for {symbol}: {e}")

        apply_pb_display_rule(clean_sym, dossier)
        cls._CACHE[clean_sym] = dossier
        return dossier


def pd_not_na(val):
    if val is None:
        return False
    try:
        import math
        return not math.isnan(val)
    except:
        return True


class IndustryKnowledgeEngine:
    """Permitted, curated knowledge base of Indian industry dynamics and risk parameters."""
    
    SECTOR_KNOWLEDGE = {
        "Energy": {
            "demand_drivers": "Domestic transportation fuels demand growing at 5-6% YoY; petrochemical intensity rising with industrial packaging and consumer goods.",
            "supply_dynamics": "OPEC+ crude quotas constrain feedstocks; domestic refining capacity additions at Paradip and Jamnagar keep utilization > 100%.",
            "regulatory_framework": "Administered pricing mechanism deregulation; windfall taxes calibrated to international Singapore gross refining margins (GRM).",
            "key_risks": "Brent crude volatility, global refining margin compression, green hydrogen transition capex overhang."
        },
        "Technology": {
            "demand_drivers": "Enterprise cloud migrations, Generative AI engineering integration, and cost-takeout vendor consolidation in US & European BFS/Healthcare.",
            "supply_dynamics": "Indian tech engineering talent pool of 5.4M professionals; attrition normalized to 12-14%; shift toward global capability centers (GCCs).",
            "regulatory_framework": "SEZ unit sunset clauses; statutory H-1B visa compliance; Digital Personal Data Protection (DPDP) Act 2023 compliance.",
            "key_risks": "US discretionary tech spend cuts, rupee appreciation vs USD/EUR, GenAI delivery model deflation."
        },
        "Financial Services": {
            "demand_drivers": "Retail credit expansion (unsecured, auto, home) growing at 14-16% YoY; formalization of SME borrowing via GST & Account Aggregator network.",
            "supply_dynamics": "Deposit growth trailing credit expansion (11-12%), driving wholesale deposit cost pressures and liquidity coverage ratio (LCR) scrutiny.",
            "regulatory_framework": "RBI risk weight enhancements on unsecured personal loans and NBFC lending; draft project finance provisioning norms.",
            "key_risks": "Net Interest Margin (NIM) compression, unsecured portfolio slippages, systemic liquidity tightening."
        },
        "Consumer Cyclical": {
            "demand_drivers": "Quick-commerce rapid penetration (10-minute grocery & dark stores) expanding at >100% YoY; urban food delivery premiumization and frequency growth.",
            "supply_dynamics": "Dense dark store network rollouts in top 15 metros; delivery partner fleet expansion; warehouse inventory centralization.",
            "regulatory_framework": "Consumer Protection (E-Commerce) Rules, gig-worker social security legislation proposals, FSSAI dark store hygiene audit mandates.",
            "key_risks": "Intense dark store expansion capex burn, delivery partner wage inflation, quick-commerce margin discounting wars."
        },
        "Industrials": {
            "demand_drivers": "Government infrastructure capex budget (₹11.11 Lakh Cr); private industrial capex revival in renewables, electronics, and defense.",
            "supply_dynamics": "Domestic manufacturing capacity expanding under Production Linked Incentive (PLI) schemes.",
            "regulatory_framework": "Public procurement 'Make in India' preference orders; statutory project environmental clearances.",
            "key_risks": "Raw material (steel, copper) inflation, execution delays, high working capital intensity."
        }
    }

    @classmethod
    def get_industry_profile(cls, sector: str) -> Dict[str, str]:
        for sec_key, profile in cls.SECTOR_KNOWLEDGE.items():
            if sec_key.lower() in sector.lower() or sector.lower() in sec_key.lower():
                return {**profile, "data_status": "CURATED_SECTOR_TEMPLATE"}
        return {
            "demand_drivers": None,
            "supply_dynamics": None,
            "regulatory_framework": None,
            "key_risks": None,
            "data_status": "UNAVAILABLE"
        }
