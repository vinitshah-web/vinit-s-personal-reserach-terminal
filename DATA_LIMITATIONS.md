# Data Limitations & Regulatory Compliance Register

This document records the official data provenance, access constraints, licensing limitations, and operational rules governing the NSE Equity Intelligence Platform.

---

## 1. Data Sources & Licensing

| Dataset | Provider | Protocol | License & Usage Terms | Limitation / Mitigation |
|---|---|---|---|---|
| **Daily Bhavcopy (EOD)** | National Stock Exchange of India (NSE) | HTTPS Archive (ZIP / CSV) | Non-commercial educational and internal research usage. Commercial redistribution prohibited. | Historical archives occasionally change header formats (e.g. legacy PR.zip vs modern CSV). Ingestion pipeline uses SHA-256 validation and legacy header adapters. |
| **Corporate Actions** | NSE Market Data / BSE Filings | HTTPS / CSV | Public domain exchange notifications. Attribution required. | Incomplete announcements (missing rights subscription prices) are flagged as `DATA_INCOMPLETE` without breaking pipelines. |
| **Financial Statements** | MCA XBRL / Exchange Filings | XBRL XML / PDF / Scraped JSON | Statutory public corporate filings. | Filings available only after publication date. Point-in-time timestamping eliminates lookahead bias. |
| **Tax Schedules & Levies** | Income Tax Dept / CBIC / SEBI | Statutory Notifications & Gazettes | Public legal statutes. | Transition from IT Act 1961 to IT Act 2025 handled via date-gated dual-regime dispatch. |

---

## 2. Ingestion and Survivorship Bias Safeguards

1. **Security Master with ISIN Mapping**:
   - Symbols frequently change (e.g., UTI Bank -> Axis Bank). All records are indexed by ISIN (`INE...`).
   - Ticker history is tracked with effective date boundaries.
2. **Point-in-Time Universe Selection**:
   - Stocks delisted or suspended in historical periods (e.g. Kingfisher Airlines) remain in the database with their respective `listing_date` and `delisting_date`.
   - Backtests running at date $T$ query active securities where $\text{listing\_date} \le T$ and $(\text{delisting\_date} > T \text{ or NULL})$.
3. **Restatement Integrity**:
   - Original statements are preserved with their historical ingestion timestamp.
   - If an annual report restates prior year figures, the restated figures are inserted as an amended statement linked to the predecessor via `supersedes_id`, preventing retrospective leakage.

---

## 3. Explicit Production Blockers & Unverified Rates

The following parameters are currently marked **UNVERIFIED** and are locked behind `UnverifiedRateError` guards in production execution:
- **NSE Transaction Charges** (currently estimated at 0.00345% turnover). Requires real-time confirmation against latest NSE circular before live execution.
- **SEBI Turnover Fee** (currently estimated at 0.0001% turnover). Requires annual Gazette/Circular check.
- **Micro-cap XBRL Filings Pre-2015**: Incomplete XBRL tagging exists for small SME listings prior to 2015. Such metrics return explicit `None` rather than fabricated approximations.
