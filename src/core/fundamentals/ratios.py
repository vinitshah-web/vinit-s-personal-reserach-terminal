"""Fundamental Accounting Ratio Calculators with Strict Sector Routing."""
from datetime import date, datetime
from typing import Any, Dict, Optional, Union


DateValue = Union[date, datetime, str]


class FundamentalAnalysisEngine:
    @staticmethod
    def _parse_date(value: DateValue) -> date:
        """Normalize supported date inputs without silently accepting timestamps."""
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return date.fromisoformat(value)

    def calculate_pb_ratio(
        self,
        price: Optional[float],
        price_date: Optional[DateValue],
        total_equity_cr: Optional[float],
        shares_outstanding_cr: Optional[float],
        balance_sheet_date: Optional[DateValue]
    ) -> Dict[str, Any]:
        """Calculate P/B only from complete, date-aligned source inputs."""
        if price is None:
            return {"pb_ratio": None, "pb_ratio_reason": "Price is unavailable."}
        if price_date is None:
            return {"pb_ratio": None, "pb_ratio_reason": "Price date is unavailable."}
        if total_equity_cr is None:
            return {"pb_ratio": None, "pb_ratio_reason": "Total equity is unavailable."}
        if shares_outstanding_cr is None:
            return {"pb_ratio": None, "pb_ratio_reason": "Shares outstanding are unavailable."}
        if balance_sheet_date is None:
            return {"pb_ratio": None, "pb_ratio_reason": "Balance-sheet date is unavailable."}
        if price <= 0:
            return {"pb_ratio": None, "pb_ratio_reason": "Price must be positive."}
        if total_equity_cr <= 0:
            return {"pb_ratio": None, "pb_ratio_reason": "Total equity must be positive."}
        if shares_outstanding_cr <= 0:
            return {"pb_ratio": None, "pb_ratio_reason": "Shares outstanding must be positive."}

        try:
            normalized_price_date = self._parse_date(price_date)
        except (TypeError, ValueError):
            return {"pb_ratio": None, "pb_ratio_reason": "Price date is invalid."}
        try:
            normalized_balance_sheet_date = self._parse_date(balance_sheet_date)
        except (TypeError, ValueError):
            return {"pb_ratio": None, "pb_ratio_reason": "Balance-sheet date is invalid."}

        if normalized_balance_sheet_date > normalized_price_date:
            return {
                "pb_ratio": None,
                "pb_ratio_reason": "Balance-sheet date cannot be after the price date."
            }

        try:
            oldest_allowed_date = normalized_price_date.replace(
                year=normalized_price_date.year - 1
            )
        except ValueError:
            # A 29-Feb price date has 28-Feb as its exact one-year boundary.
            oldest_allowed_date = normalized_price_date.replace(
                year=normalized_price_date.year - 1,
                day=28
            )

        if normalized_balance_sheet_date < oldest_allowed_date:
            return {
                "pb_ratio": None,
                "pb_ratio_reason": "Balance sheet is more than 12 months older than the price date."
            }

        book_value_per_share = total_equity_cr / shares_outstanding_cr
        return {
            "pb_ratio": round(price / book_value_per_share, 2),
            "pb_ratio_reason": None
        }

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
