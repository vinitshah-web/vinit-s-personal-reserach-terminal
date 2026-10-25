# NSE Equity Research Assistant — Online + Local Windows Terminal

An INR-first, personal equity research and investment analysis platform for the National Stock Exchange of India (NSE). Designed for retail and personal investment research with institutional rigor, transparent provenance, and zero mandatory spending.

---

## 🌐 Live Online Application (Mode A)
👉 **[https://vinitshah-web.github.io/vinit-s-personal-reserach-terminal/](https://vinitshah-web.github.io/vinit-s-personal-reserach-terminal/)**

- **Zero Installation Required:** Access directly in any modern web browser.
- **Client-Side Security Master:** Autocomplete search across all 3,392 active NSE listed equities.
- **Keyless Real-Time Prices:** Direct browser integration with TejHQ open edge APIs (`api.tejhq.dev`) for official NSE end-of-day closing bhavcopies and corporate actions.
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

## 🧪 Comprehensive Verification Suite (92 / 92 Tests Passing)

Execute the full automated test suite verifying all 12 Retail Research Assistant acceptance criteria, valuation models, and statutory Indian tax rules:

```powershell
py -m pytest tests/ -v
```

```text
tests/test_retail_research_assistant.py::test_1_stock_autocomplete_and_ambiguous_resolution PASSED
tests/test_retail_research_assistant.py::test_2_selected_company_propagation PASSED
tests/test_retail_research_assistant.py::test_3_quote_source_date_freshness_and_missing_handling PASSED
tests/test_retail_research_assistant.py::test_4_financial_units_periods_and_inr_first PASSED
tests/test_retail_research_assistant.py::test_5_peer_selection_and_comparative_metrics PASSED
tests/test_retail_research_assistant.py::test_6_independent_valuation_calculations_and_scenarios PASSED
tests/test_retail_research_assistant.py::test_7_missing_or_conflicting_data_fails_open_with_disclosure PASSED
tests/test_retail_research_assistant.py::test_8_ai_provider_absence_fallback_report_generation PASSED
tests/test_retail_research_assistant.py::test_9_valid_pdf_creation_and_company_identity PASSED
tests/test_retail_research_assistant.py::test_10_local_startup_and_workflow_without_paid_credentials PASSED
tests/test_retail_research_assistant.py::test_11_online_static_files_integrity PASSED
tests/test_retail_research_assistant.py::test_12_no_secrets_exposed PASSED
================================ 92 passed in 14.06s ================================
```

---

## 🏛️ Indian Statutory Taxation & Currency Framework
- **INR-First:** All prices in ₹, company values in ₹ Crores, and readable Indian numbering (`₹16,10,364 Cr`, `₹1.25 Lakh`).
- **Direct Tax Code (2025):** STCG 20% (Sec 196), LTCG 12.5% (Sec 198) with ₹1.25L exemption, intra-head loss set-off rules (Sec 108), and dividend withholding rules (Sec 393).
