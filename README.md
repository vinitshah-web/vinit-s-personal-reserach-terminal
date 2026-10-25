# NSE Equity Intelligence Platform

Institutional-grade quantitative research and equity analysis engine for the National Stock Exchange of India (NSE).

## Key Features

1. **Dual-Era Indian Tax Engine**: Seamlessly models the transition from the legacy Income-tax Act, 1961 to the modern Income-tax Act, 2025 (effective 1 April 2026), incorporating updated STCG (20%), LTCG (12.5% above ₹1.25 Lakhs / Tax Year), and dividend TDS rules.
2. **Mathematically Airtight Corporate Actions**: Computes split, bonus, and rights (TERP) price adjustment factors, volume divisors, and total return indices with dividend reinvestment at ex-date close.
3. **Point-in-Time Integrity**: Distinguishes `published_at`, `ingested_at`, and `restated_at` to prevent lookahead and restatement bias.
4. **Sector-Specific Fundamentals**: Enforces DuPont 5-Factor analysis for non-financials while strictly routing Banks/NBFCs to specialized NIM, CASA, and GNPA models.

## Quickstart (Windows / PowerShell)

```powershell
# 1. Setup environment and database
.\scripts\setup.ps1

# 2. Execute automated test suite
.\scripts\run_tests.ps1

# 3. View UI Prototypes
py -m http.server 8080 --directory ui/prototypes
# Open http://localhost:8080/overview.html or http://localhost:8080/stock_intelligence.html
```
