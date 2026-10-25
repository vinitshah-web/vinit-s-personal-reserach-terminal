"""Institutional Research Report Generator.
Generates institutional equity tear-sheets and deep-dive reports.
Mandatory header and watermark: CODE TEST — SYNTHETIC DATA.
"""
from datetime import date, datetime, timezone
from typing import Dict, Any, Optional
import os


class ResearchReportGenerator:
    """Produces standardized institutional equity research tear-sheets."""

    @staticmethod
    def generate_markdown_tearsheet(data: Dict[str, Any]) -> str:
        """
        Formats comprehensive 3-part structured research tear-sheet in Markdown.
        Carries mandatory institutional synthetic watermark.
        """
        ticker = data.get("ticker", "UNKNOWN")
        isin = data.get("isin", "UNKNOWN")
        company = data.get("company_name", ticker)
        sector = data.get("sector", "N/A")
        price = data.get("current_price", 0.0)
        is_financial = data.get("is_financial", False)

        md = f"""# INSTITUTIONAL EQUITY RESEARCH TEARSHEET
> **WATERMARK:** `CODE TEST — SYNTHETIC DATA — FOR DEMONSTRATION ONLY`  
> **DISCLAIMER:** Not investment advice. Prepared strictly under quantitative verification protocol.

---

## 1. Security Overview & Identification
- **Company Name:** {company}
- **NSE Ticker:** `{ticker}`
- **ISIN:** `{isin}`
- **Sector / Industry:** {sector}
- **Classification:** {"Financial Institution (Banking / NBFC)" if is_financial else "Non-Financial Corporate"}
- **Latest Close:** ₹{price:,.2f}
- **Report Date:** {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}

---

## 2. Fundamental & Financial Profile (TTM)
"""
        if not is_financial:
            rev = data.get("ttm_revenue_cr", 0.0)
            ebitda = data.get("ttm_ebitda_cr", 0.0)
            pat = data.get("ttm_pat_cr", 0.0)
            roe = data.get("dupont_roe_pct", 0.0)
            tax_b = data.get("tax_burden", 0.0)
            int_b = data.get("interest_burden", 0.0)
            margin = data.get("ebit_margin_pct", 0.0)
            at = data.get("asset_turnover", 0.0)
            em = data.get("equity_multiplier", 0.0)

            md += f"""### DuPont 5-Factor ROE Breakdown (Palepu & Healy 2019)
- **TTM Revenue:** ₹{rev:,.2f} Cr
- **TTM EBITDA:** ₹{ebitda:,.2f} Cr
- **TTM PAT (Net Income):** ₹{pat:,.2f} Cr
- **Product ROE:** **{roe:.2f}%**

| Factor | Metric Name | Value | Analytical Interpretation |
| :--- | :--- | :--- | :--- |
| **Factor 1** | Tax Burden (PAT / EBT) | {tax_b:.4f} | Retention after corporate tax |
| **Factor 2** | Interest Burden (EBT / EBIT) | {int_b:.4f} | Solvency & debt service cushion |
| **Factor 3** | Operating Margin (EBIT / Rev) | {margin:.2f}% | Pure operational pricing power |
| **Factor 4** | Asset Turnover (Rev / Assets) | {at:.4f}x | Balance sheet capital velocity |
| **Factor 5** | Financial Leverage (Assets / Eq) | {em:.4f}x | Financial gearing multiplier |
"""
        else:
            nim = data.get("nim_pct", 0.0)
            casa = data.get("casa_pct", 0.0)
            gnpa = data.get("gnpa_pct", 0.0)
            roe = data.get("roe_pct", 0.0)
            md += f"""### Banking Asset Quality & Spread Ratios (RBI Master Direction)
- **Net Interest Margin (NIM):** **{nim:.2f}%**
- **CASA Ratio:** **{casa:.2f}%** (Low-cost franchise strength)
- **Gross NPA Ratio:** **{gnpa:.2f}%** (Underwriting prudence)
- **Return on Equity (ROE):** **{roe:.2f}%**
"""

        md += f"""
---

## 3. Quantitative Valuation & Implied Growth (Reverse DCF)
"""
        if not is_financial:
            ev = data.get("enterprise_value_cr", 0.0)
            fair_per_share = data.get("fair_value_per_share", 0.0)
            implied_g = data.get("reverse_dcf_implied_growth_pct", 0.0)
            wacc = data.get("wacc_pct", 12.0)
            term_g = data.get("terminal_growth_pct", 4.0)

            md += f"""- **Model:** Damodaran Free Cash Flow to Firm (FCFF) Unrounded Discounting
- **Calculated Enterprise Value:** ₹{ev:,.2f} Cr
- **Model Fair Value Per Share:** ₹{fair_per_share:,.2f}
- **Assumed WACC:** {wacc:.2f}% | **Terminal Growth:** {term_g:.2f}%
- **Reverse DCF Implied Growth:** **{implied_g:.2f}%**
  *(Market price currently prices in {implied_g:.2f}% discrete 5-year FCFF CAGR)*
"""
        else:
            ddm_val = data.get("ddm_fair_value_cr", 0.0)
            payout = data.get("dividend_payout_pct", 0.0)
            md += f"""- **Model:** Regulatory Capital Retention Banking DDM
- **Dividend Payout Ratio:** {payout:.2f}%
- **Implied Fair Value:** ₹{ddm_val:,.2f} Cr
"""

        p5 = data.get("mc_p5_1yr", 0.0)
        p50 = data.get("mc_p50_1yr", 0.0)
        p95 = data.get("mc_p95_1yr", 0.0)
        mdd = data.get("median_drawdown_pct", 0.0)
        prob_pos = data.get("prob_positive_1yr_pct", 0.0)

        md += f"""
---

## 4. Forecasting & Monte Carlo Scenario Distribution (1-Year)
*Stationary block bootstrapping (4-week blocks) across 1,000 resampled paths.*

| Scenario Percentile | Projected 1-Yr Price | Implied Return |
| :--- | :--- | :--- |
| **5th Percentile (Severe Bear)** | ₹{p5:,.2f} | {((p5/price - 1.0)*100.0 if price > 0 else 0.0):+.1f}% |
| **50th Percentile (Median Base)** | ₹{p50:,.2f} | {((p50/price - 1.0)*100.0 if price > 0 else 0.0):+.1f}% |
| **95th Percentile (Bull Case)** | ₹{p95:,.2f} | {((p95/price - 1.0)*100.0 if price > 0 else 0.0):+.1f}% |

- **Probability of Positive 1-Year Return:** **{prob_pos:.1f}%**
- **Median Maximum Drawdown:** **{mdd:.1f}%**

---

## 5. Technicals & Regime Classification
- **50-Day Moving Average:** ₹{data.get("dma_50", 0.0):,.2f}
- **200-Day Moving Average:** ₹{data.get("dma_200", 0.0):,.2f}
- **Wilder RSI (14):** {data.get("rsi_14", 50.0):.1f}
- **Benchmark Market Regime:** `{data.get("market_regime", "BULL_QUIET")}`

---

## 6. Corporate Governance & Long-Term Drivers
- **Promoter Pledging:** {data.get("promoter_pledge_pct", 0.0):.1f}% (`{data.get("pledge_risk_level", "LOW")}`)
- **Auditor Turnover:** {data.get("auditor_resignation_count", 0)} in past 3 years (`{data.get("auditor_risk_level", "CLEAN")}`)
- **Revenue Driver Classification:** `{data.get("driver_classification", "VOLUME_LED")}`
- **10-Year Industry 15%+ Base Rate:** {data.get("industry_10yr_base_rate_pct", 15.0):.1f}% (Corrected for {data.get("delisting_mortality_pct", 20.0):.1f}% delisting/consolidation mortality)

---
*Generated by NSE Equity Intelligence Platform — Phase 11 Institutional Reporting Protocol.*
"""
        return md
