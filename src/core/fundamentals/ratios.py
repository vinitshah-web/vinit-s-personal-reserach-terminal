"""Fundamental Accounting Ratio Calculators with Strict Sector Routing."""
from typing import Dict, Any


class FundamentalAnalysisEngine:
    def calculate_dupont_5factor(
        self,
        net_income: float,
        ebt: float,
        ebit: float,
        revenue: float,
        total_assets: float,
        equity: float,
        is_financial: bool = False
    ) -> Dict[str, Any]:
        """
        Calculates 5-Step DuPont ROE decomposition:
        ROE = Tax Burden x Interest Burden x EBIT Margin x Asset Turnover x Equity Multiplier
        Strictly disallowed for Banks and NBFCs.
        """
        if is_financial:
            raise ValueError("DuPont 5-Factor ROE is not applicable to financial institutions (Banks/NBFCs). Use NIM / Spread models.")

        if ebt == 0 or ebit == 0 or revenue == 0 or total_assets == 0 or equity == 0:
            raise ValueError("Denominator in DuPont decomposition cannot be zero.")

        tax_burden = round(net_income / ebt, 4)
        interest_burden = round(ebt / ebit, 4)
        ebit_margin = round(ebit / revenue, 4)
        asset_turnover = round(revenue / total_assets, 4)
        equity_multiplier = round(total_assets / equity, 4)

        product_roe = round(tax_burden * interest_burden * ebit_margin * asset_turnover * equity_multiplier, 4)
        direct_roe = round(net_income / equity, 4)

        return {
            "tax_burden": tax_burden,
            "interest_burden": interest_burden,
            "ebit_margin": ebit_margin,
            "asset_turnover": asset_turnover,
            "equity_multiplier": equity_multiplier,
            "roe_product": product_roe,
            "roe_direct": direct_roe,
            "discrepancy": round(abs(product_roe - direct_roe), 4)
        }

    def calculate_ev_ebitda(
        self,
        market_cap: float,
        total_debt: float,
        cash_equivalents: float,
        ebitda_ttm: float,
        is_financial: bool = False
    ) -> Dict[str, float]:
        """Calculates Enterprise Value to EBITDA for non-financials."""
        if is_financial:
            raise ValueError("EBITDA and EV/EBITDA cannot be calculated for Banks or Financial Institutions.")
        if ebitda_ttm <= 0:
            raise ValueError("EBITDA must be positive to calculate EV/EBITDA multiple.")

        ev = market_cap + total_debt - cash_equivalents
        multiple = round(ev / ebitda_ttm, 2)
        return {
            "enterprise_value": ev,
            "ev_ebitda": multiple
        }

    def calculate_banking_metrics(
        self,
        interest_earned: float,
        interest_expended: float,
        avg_earning_assets: float,
        casa_deposits: float,
        total_deposits: float,
        gross_npa: float,
        gross_advances: float
    ) -> Dict[str, float]:
        """Calculates standard banking fundamental metrics (NIM, CASA, GNPA)."""
        if avg_earning_assets <= 0 or total_deposits <= 0 or gross_advances <= 0:
            raise ValueError("Banking balance sheet denominators must be strictly positive.")

        net_interest_income = interest_earned - interest_expended
        nim = round(net_interest_income / avg_earning_assets, 4)
        casa_ratio = round(casa_deposits / total_deposits, 4)
        gnpa_ratio = round(gross_npa / gross_advances, 4)

        return {
            "net_interest_income": net_interest_income,
            "net_interest_margin": nim,
            "casa_ratio": casa_ratio,
            "gnpa_ratio": gnpa_ratio
        }
