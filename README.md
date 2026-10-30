# NSE Equity Research Assistant — Online + Local Windows Terminal

An INR-first, personal equity research and investment analysis platform for the National Stock Exchange of India (NSE). Designed for retail and personal investment research with institutional rigor, transparent provenance, and zero mandatory spending.

---

## 🌐 Live Online Application (Mode A)
👉 **[https://vinitshah-web.github.io/vinit-s-personal-reserach-terminal/](https://vinitshah-web.github.io/vinit-s-personal-reserach-terminal/)**

- **Zero Installation Required:** Access directly in any modern web browser.
- **Client-Side Security Master:** Autocomplete search across all 3,392 active NSE listed equities.
- **Verified Daily EOD Prices:** Direct browser integration with TejHQ (`api.tejhq.dev`) for NSE end-of-day bhavcopy data. This is official-close research data, not an intraday trading feed.
- **Client-Side Persistence:** Save watchlists, research histories, and export reports via browser storage with zero external database subscriptions.

---

## 💻 Local Windows Application (Mode B)

Run the full Python backend on your Windows laptop with local SQLite storage and vector PDF generation:

```powershell
# 1. Clone repository
git clone https://github.com/vinitshah-web/vinit-s-personal-reserach-terminal.git
cd vinit-s-personal-reserach-terminal

# 2. Run the 1-Click Startup Script (starts FastAPI server & opens browser)
powershell -ExecutionPolicy Bypass -File .\run_local.ps1
```

The application automatically checks dependencies, launches on `http://127.0.0.1:8000`, and opens your default browser.

### Daily refresh

`run_local.ps1` checks for a newer validated NSE snapshot every time the terminal starts. The refresh is atomic: an incomplete snapshot, impossible OHLC values, duplicate ISIN, stale provider status, or insufficient market coverage leaves the last verified data untouched.

To refresh automatically after market close even when the terminal is closed, register the per-user Windows task once:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\register_daily_refresh.ps1
```

The default schedule is 19:45 local time with a 22:00 retry and assumes the Windows system time zone is IST, spanning TejHQ's documented 18:30 publication and 21:30 retry windows. Change them with `-DailyTime "20:15" -RetryTime "22:15"`. Manual refresh is also available:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\refresh_daily.ps1
```

The API endpoint `GET /api/v1/market-data/status` reports the latest local trading date, provider publication time, fetch time, row count, and SHA-256 snapshot hash.

---

## 🚀 Primary User Journey
1. **Search Stock:** Instant fuzzy autocomplete across 3,392 active NSE equities by Symbol, Company Name, or ISIN.
2. **View Price & Summary:** Verified EOD closing price in ₹, quote date, source provenance (TejHQ Keyless EOD / NSE Bhavcopy), and market capitalization in ₹ Crores.
3. **Understand the Business:** Plain-language summary of core operations, segments, and market footprint.
4. **Review Financial Performance:** 5-year reported financial statements (Revenue, EBITDA, Net Profit, Operating Cash Flow, Capex, Free Cash Flow, Debt, Cash in ₹ Cr).
5. **Analyze Industry Dynamics:** Curated demand drivers, domestic supply capacity, PLI initiatives, and statutory regulatory framework.
6. **Inspect Valuation Scenarios:** Automatic FCFF DCF for industrials / DDM for banks with Bear, Base, and Bull fair-value scenarios in ₹/share, plus Reverse DCF implied growth analysis.
7. **Examine Risks:** Key catalysts, competitive threats, and quantifiable thesis invalidation triggers.
8. **Export Vector PDF Report:** 1-Click download of a multi-page, formatted vector PDF research report using ReportLab with zero paid software.

---

## 💎 Zero-Budget Operating Policy & Data Providers

| Provider / Tool | Data Provided | Free Tier Policy | Authentication |
| :--- | :--- | :--- | :--- |
| **TejHQ Open EOD API** | Daily NSE/BSE closing bhavcopies, OHLCV, volume, and corporate actions | Keyless Free Tier from Cloudflare Edge | **None required (Keyless)** |
| **Yahoo Finance / Disclosures** | Business profiles, 5-year financial statements, trailing multiples, and 52W range | Open public corporate disclosures | **None required** |
| **Local SQLite (`nse_platform.db`)** | 3,392 listed equities, historical prices, and corporate action records | Open-source file database | **None required** |
| **ReportLab 5.0** | Institutional vector PDF equity research generation in INR | Open-source BSD Python library | **None required** |
| **Google Gemini API (Optional)** | Optional AI-generated executive summaries and qualitative commentary | Free Tier: 15 RPM, 1,500 RPD ($0/mo) | *Optional API Key in `.env`* |

> **Honest Coverage Notice:** If a small-cap company lacks multi-year digital filings or quotes, the platform cleanly displays a **"Data Unavailable"** state. It **never** fabricates synthetic financial records.

---

## 🧪 Comprehensive Verification Suite

Execute the full automated test suite verifying all 12 Retail Research Assistant acceptance criteria, valuation models, and statutory Indian tax rules:

```powershell
py -m pytest tests/ -v
```

The suite includes offline acceptance tests and atomic daily-refresh tests. The live provider is tested separately because a passing mock cannot prove the provider's current trading date or price.

---

## 🏛️ Indian Statutory Taxation & Currency Framework
- **INR-First:** All prices in ₹, company values in ₹ Crores, and readable Indian numbering (`₹16,10,364 Cr`, `₹1.25 Lakh`).
- **Direct Tax Code (2025):** STCG 20% (Sec 196), LTCG 12.5% (Sec 198) with ₹1.25L exemption, intra-head loss set-off rules (Sec 108), and dividend withholding rules (Sec 393).
