# Formula & Model Verification Registry

This registry tracks authoritative citations, effective dates, mathematical expressions, numerical test fixtures, and verification statuses for all financial metrics and models implemented in the platform.

---

## 1. DuPont 5-Factor ROE Decomposition
- **Formula ID**: `DUPONT_ROE_5FACTOR`
- **Category**: Fundamental Accounting Ratio
- **Applicability**: Non-financial corporations only (strictly excluded for Banks and NBFCs)
- **Expression**:
  $$\text{ROE} = \left(\frac{\text{PAT}}{\text{EBT}}\right) \times \left(\frac{\text{EBT}}{\text{EBIT}}\right) \times \left(\frac{\text{EBIT}}{\text{Sales}}\right) \times \left(\frac{\text{Sales}}{\text{Total Assets}}\right) \times \left(\frac{\text{Total Assets}}{\text{Net Worth}}\right)$$
- **Terms**:
  1. Tax Burden = $\text{PAT} / \text{EBT}$
  2. Interest Burden = $\text{EBT} / \text{EBIT}$
  3. Operating Margin = $\text{EBIT} / \text{Sales}$
  4. Asset Turnover = $\text{Sales} / \text{Total Assets}$
  5. Equity Multiplier = $\text{Total Assets} / \text{Net Worth}$
- **Authoritative Citation**: Palepu, Healy & Peek, *Business Analysis and Valuation: IFRS Edition*, 6th ed. (2019), Chapter 5, pp. 218–224.
- **Verification Status**: ✅ Verified
- **Numerical Test Fixture**:
  - Net Income = 120.0, EBT = 160.0, EBIT = 200.0, Revenue = 1000.0, Assets = 2000.0, Equity = 800.0
  - Factors: $0.75 \times 0.80 \times 0.20 \times 0.50 \times 2.50 = 0.1500$
  - Direct ROE: $120.0 / 800.0 = 0.1500$ (Matches to $10^{-6}$)

---

## 2. Enterprise Value to EBITDA
- **Formula ID**: `VAL_EV_EBITDA`
- **Category**: Valuation Multiple
- **Applicability**: Non-financial corporations only
- **Expression**:
  $$\text{EV} = \text{Market Cap} + \text{Total Debt} - \text{Cash \& Equivalents}$$
  $$\text{EV/EBITDA} = \frac{\text{EV}}{\text{EBITDA}_{\text{TTM}}}$$
- **Authoritative Citation**: Damodaran, A., *Investment Valuation*, 3rd ed. (2012), Chapter 20.
- **Verification Status**: ✅ Verified

---

## 3. Discounted Cash Flow (FCFF)
- **Formula ID**: `VAL_DCF_FCFF`
- **Category**: Intrinsic Valuation Model
- **Applicability**: Non-financial corporations
- **Expression**:
  $$\text{FCFF} = \text{EBIT} \times (1 - t) + \text{Depreciation} - \text{CapEx} - \Delta\text{Working Capital}$$
  $$\text{EV} = \sum_{t=1}^{n} \frac{\text{FCFF}_t}{(1 + \text{WACC})^t} + \frac{\text{FCFF}_n \times (1 + g)}{(\text{WACC} - g)(1 + \text{WACC})^n}$$
- **Authoritative Citation**: Damodaran, A., *Investment Valuation*, 3rd ed. (2012), Chapter 15.
- **Verification Status**: ✅ Verified against textbook numerical fixture (EV = 919.64 Cr).

---

## 4. Reverse DCF Solver
- **Formula ID**: `VAL_REVERSE_DCF`
- **Category**: Expectation Implied Growth Analysis
- **Method**: Bisection root-finding on $g \in [-0.10, 0.50]$ matching model enterprise value to observed market capitalization + net debt.
- **Verification Status**: ✅ Verified for Numerical Consistency (Round-trip identity within ₹0.01 tolerance). Labeled "Solver Numerical Consistency Verified — Not Real-World Forecast Accuracy".

---

## 5. Banking Fundamentals (NIM & Asset Quality)
- **Formula ID**: `BANK_NIM`
  - Expression: $\text{NIM} = \frac{\text{Interest Earned} - \text{Interest Expended}}{\text{Average Total Assets}}$
  - Authoritative Citation: Reserve Bank of India (RBI) Master Direction – Financial Statements - Presentation and Disclosures (2021).
  - Status: ✅ Verified
- **Formula ID**: `BANK_GNPA_RATIO`
  - Expression: $\text{GNPA Ratio} = \frac{\text{Gross Non-Performing Assets}}{\text{Gross Advances}}$
  - Authoritative Citation: RBI Prudential Norms on Income Recognition, Asset Classification and Provisioning (IRACP).
  - Status: ✅ Verified

---

## 6. Corporate Action Price Adjustment & TERP
- **Formula ID**: `CA_ADJUSTMENT_FACTORS`
  - Split: $f = 1/n$
  - Bonus: $f = e / (e + b)$
  - Rights TERP: $\text{TERP} = \frac{P_{\text{cum}} \cdot n_{\text{old}} + P_{\text{sub}} \cdot n_{\text{new}}}{n_{\text{old}} + n_{\text{new}}}, \quad f = \frac{\text{TERP}}{P_{\text{cum}}}$
  - Cumulative Factor: $F(t) = \prod_{i : d_i > t} f_i$
  - Authoritative Citation: NSE India Corporate Actions Adjustment Methodology & SEBI ICDR Regulations.
  - Status: ✅ Verified against 8 independent fixtures.

---

## 7. Total Return Index with Dividend Reinvestment
- **Formula ID**: `TOTAL_RETURN_DIV_REINVEST`
  - Ex-Date Dividend Adjustment: $D_{\text{adj}}(d) = D_{\text{raw}}(d) \times F(d)$
  - Total Return Compounding: $\text{TR}(d) = \text{TR}(d-1) \times \frac{\text{close\_adj}(d) + D_{\text{adj}}(d)}{\text{close\_adj}(d-1)}$
  - Status: ✅ Verified across combined split-dividend and bonus-dividend sequence tests.
