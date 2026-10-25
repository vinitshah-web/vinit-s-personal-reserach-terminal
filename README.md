# Vinit's Self-Made Research Terminal

Institutional-grade quantitative research and equity analysis engine for the National Stock Exchange of India (NSE).

> **MANDATORY WATERMARK:** `CODE TEST — SYNTHETIC DATA — FOR DEMONSTRATION ONLY`  
> Prepared strictly under quantitative verification protocol.

---

## Key Capabilities

1. **Dual-Era Statutory Indian Tax Engine ([`src/tax/engine.py`](file:///c:/Users/vshah/OneDrive/Desktop/tirth/src/tax/engine.py))**:
   - Seamlessly models the transition from the legacy Income-tax Act, 1961 (< 2026-04-01) to the modern Income-tax Act, 2025 (>= 2026-04-01).
   - STCG: Sec 111A $\to$ Sec 196 (20%).
   - LTCG: Sec 112A $\to$ Sec 198 (12.5% above ₹1.25 Lakh annual exemption bucket resetting each April 1).
   - Intra-head loss set-off: Sec 70 $\to$ Sec 108 (STCL sets off against both STCG and LTCG; LTCL strictly prohibited against STCG).
   - Loss carry-forward: Sec 74 $\to$ Sec 111 (8 tax years) protected under Sec 536 transition provisions.
   - Dividend TDS: Sec 194 $\to$ Sec 393(1) Table Sl. 7 (₹10,000 threshold strictly for resident individuals; Nil threshold for domestic corporates).
   - No-PAN Penal Withholding: Sec 206AA $\to$ Sec 397(2) (20% flat).
   - GST: 18% under CGST Rate Notification 11/2017 SAC 997152 strictly on fees/brokerage; STT and Stamp Duty excluded under Sec 15(2)(a).

2. **Mathematically Exact Corporate Actions ([`src/core/adjustments.py`](file:///c:/Users/vshah/OneDrive/Desktop/tirth/src/core/adjustments.py) & [`src/core/total_return.py`](file:///c:/Users/vshah/OneDrive/Desktop/tirth/src/core/total_return.py))**:
   - Splits, bonuses, and rights issues (TERP).
   - Total return index with dividend reinvestment at ex-date close across 3 distinct investor strategies (`subscribe`, `sell_renounce`, `lapse`).
   - Cumulative adjustment factors $F(t)$ maintaining raw prices completely immutable.

3. **Point-in-Time Integrity & Delisting Protection ([`src/core/universe.py`](file:///c:/Users/vshah/OneDrive/Desktop/tirth/src/core/universe.py))**:
   - Distinguishes publication time (`published_at`), platform ingestion time (`ingested_at`), and restatement time (`restated_at`).
   - Supports dual modes: `AS_KNOWN` (operational zero-lookahead) and `RECONSTRUCTED` (audited restatement).
   - Delisted companies (e.g. Kingfisher Airlines) remain archived with lifetime dates to guarantee survivorship-bias-free backtesting.

4. **Institutional Fundamental & Valuation Core ([`src/core/fundamentals/`](file:///c:/Users/vshah/OneDrive/Desktop/tirth/src/core/fundamentals/) & [`src/core/valuation.py`](file:///c:/Users/vshah/OneDrive/Desktop/tirth/src/core/valuation.py))**:
   - DuPont 5-Factor ROE decomposition (Palepu & Healy 2019) strictly enforced for non-financials and rejected for financial institutions.
   - Specialized banking metrics: NIM, CASA, GNPA, and Regulatory Capital DDM ($b = g/\text{ROE}$).
   - Unrounded Damodaran FCFF ($EV = 919.6616\text{ Cr}$) and Reverse DCF implied growth solver.

5. **Quantitative Forecasting, Technicals & Backtesting**:
   - 50/200-DMA, Wilder RSI(14), and ATR(14) computed on `close_adj` (immune to bonus drops).
   - Indian Equity Market Regime filter (BULL_QUIET, BULL_VOLATILE, BEAR_VOLATILE, BEAR_QUIET).
   - 52-week Monte Carlo block bootstrap scenario distribution.
   - Strategy backtester modeling full transaction frictions and dual-era statutory taxes.

---

## Quickstart (Windows / PowerShell)

### 1. Database Migrations
```powershell
py -m alembic upgrade head
```

### 2. Ingest Official NSE Daily Archives
```powershell
py scripts/ingest_real_archives.py
```
Ingests 2,915 securities, 5,823 raw prices across 22-Oct and 23-Oct 2026, 834 SEBI LODR corporate events, 16 corporate actions, and 246 trading days of NIFTY 50 index levels.

### 3. Run Automated 78-Test Verification Suite
```powershell
py -m pytest tests/ -v
```
All 78 unit, integration, and statutory tax tests pass in under 3.0 seconds.

### 4. Run Comprehensive Performance Benchmarks
```powershell
py scripts/benchmark.py
```

### 5. Institutional Analyst CLI ([`cli.py`](file:///c:/Users/vshah/OneDrive/Desktop/tirth/cli.py))
```powershell
# Security master summary & latest market close
py cli.py summary INE002A01018

# Damodaran FCFF intrinsic valuation
py cli.py dcf --fcff 60.0 --growth 0.08 --wacc 0.12 --terminal 0.04

# Reverse DCF implied growth solver
py cli.py reverse-dcf --ev 919.6616 --fcff 60.0 --wacc 0.12 --terminal 0.04

# Banking Regulatory Capital DDM
py cli.py banking-ddm --ni 1000 --roe 0.16 --growth 0.05 --ke 0.13

# Market Regime analysis on live Nifty 50 series
py cli.py regime

# Display complete institutional research tear-sheet
py cli.py tearsheet RELIANCE
```

### 6. FastAPI Service & Live Interactive Prototypes
```powershell
py -m uvicorn src.api.main:app --port 8000
```
Then navigate in your browser to:
- **Terminal Overview**: `http://localhost:8000/ui/overview.html`
- **Stock Intelligence**: `http://localhost:8000/ui/stock_intelligence.html`
- **Valuation Lab**: `http://localhost:8000/ui/valuation_lab.html`
- **Quant Lab**: `http://localhost:8000/ui/quant_lab.html`
- **Data Quality & Audit**: `http://localhost:8000/ui/data_quality.html`
- **Interactive OpenAPI Docs**: `http://localhost:8000/docs`

---

## Documentation Registry

- [`FORMULA_REGISTRY.md`](file:///c:/Users/vshah/OneDrive/Desktop/tirth/FORMULA_REGISTRY.md): Authoritative mathematical citations, exact unrounded figures, and numerical fixtures.
- [`DATA_LIMITATIONS.md`](file:///c:/Users/vshah/OneDrive/Desktop/tirth/DATA_LIMITATIONS.md): Data provenance, licensing constraints, and fail-closed safety guards for unverified rates.
- [`PHASE_LOG.md`](file:///c:/Users/vshah/OneDrive/Desktop/tirth/PHASE_LOG.md): Full chronological audit log of all 11 phases and verification evidence.
