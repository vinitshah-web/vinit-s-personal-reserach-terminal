# Formula & Model Verification Registry (v6.1 Final)

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

## 3. Discounted Cash Flow (FCFF) — Exact Unrounded
- **Formula ID**: `VAL_DCF_FCFF`
- **Category**: Intrinsic Valuation Model
- **Applicability**: Non-financial corporations
- **Expression**:
  $$\text{FCFF}_t = \text{FCFF}_0 \times (1 + g)^t$$
  $$\text{PV} = \sum_{t=1}^{5} \frac{\text{FCFF}_t}{(1 + \text{WACC})^t} + \frac{\text{FCFF}_5 \times (1 + g_{\text{term}})}{(\text{WACC} - g_{\text{term}})(1 + \text{WACC})^5}$$
- **Authoritative Citation**: Damodaran, A., *Investment Valuation*, 3rd ed. (2012), Chapter 15.
- **Exact Floating-Point Verification Fixture**:
  - $\text{FCFF}_0 = 60.0, g = 8.0\%, \text{WACC} = 12.0\%, g_{\text{term}} = 4.0\%$.
  - Discrete PV sum = $269.347339\text{ Cr}$
  - Terminal Value at Year 5 = $1146.075900\text{ Cr}$
  - PV of Terminal Value = $650.314244\text{ Cr}$
  - Total Enterprise Value = $\mathbf{919.661583\text{ Cr}}$ (Verified to 4 decimal places: $919.6616\text{ Cr}$).
- **Verification Status**: ✅ Verified for Formula Correctness.

---

## 4. Reverse DCF Solver
- **Formula ID**: `VAL_REVERSE_DCF`
- **Category**: Expectation Implied Growth Analysis
- **Method**: Bisection root-finding on $g \in [-0.10, 0.50]$ matching model enterprise value to target.
- **Verification Status**: ✅ Verified for Numerical Consistency of Solver (Converges back to $8.00\%$ from $EV = 919.6616$ with tolerance $< 0.01\%$).

---

## 5. Banking Fundamentals & DDM (Sustainable Payout)
- **Formula ID**: `BANK_DDM_SUSTAINABLE`
  - Expression: $\text{Retention Ratio } b = \frac{g}{\text{ROE}}, \quad \text{Dividend}_1 = \text{Net Income}_0 \times (1 - b) \times (1 + g), \quad \text{Value} = \frac{D_1}{k_e - g}$
  - Note: Strictly forbids using Net Income as direct dividend proxy.
  - Status: ✅ Verified
- **Formula ID**: `BANK_NIM`
  - Expression: $\text{NIM} = \frac{\text{Interest Earned} - \text{Interest Expended}}{\text{Average Total Assets}}$
  - Status: ✅ Verified
- **Formula ID**: `BANK_GNPA_RATIO`
  - Expression: $\text{GNPA Ratio} = \frac{\text{Gross Non-Performing Assets}}{\text{Gross Advances}}$
  - Status: ✅ Verified

---

## 6. Corporate Action Price Adjustment & TERP
- **Formula ID**: `CA_ADJUSTMENT_FACTORS`
  - Split: $f = 1/n$
  - Bonus: $f = e / (e + b)$
  - Rights TERP: $\text{TERP} = \frac{P_{\text{cum}} \cdot n_{\text{old}} + P_{\text{sub}} \cdot n_{\text{new}}}{n_{\text{old}} + n_{\text{new}}}, \quad f = \frac{\text{TERP}}{P_{\text{cum}}}$
  - Cumulative Factor: $F(t) = \prod_{i : d_i > t} f_i$
  - Status: ✅ Verified

---

## 7. Total Return Index & Rights Issue Investor Paths
- **Formula ID**: `TOTAL_RETURN_RIGHTS_STRATEGIES`
  - Ex-Date Dividend Adjustment: $D_{\text{adj}}(d) = D_{\text{raw}}(d) \times F(d)$
  - Reinvestment at ex-date close: $\text{TR}(d) = \text{TR}(d-1) \times \frac{\text{close\_adj}(d) + D_{\text{adj}}(d)}{\text{close\_adj}(d-1)}$
  - Rights Strategy 1: Subscribe (Exercises entitlement at $P_{\text{sub}}$)
  - Rights Strategy 2: Sell / Renounce (Sells rights in market at $P_{\text{cum}} - \text{TERP}$)
  - Rights Strategy 3: Lapse (Permits expiry, incurring dilution loss $f_{\text{rights}} - 1$)
  - Missing parameters: Fails closed with `IncompleteRightsDataError`.
  - Status: ✅ Verified
