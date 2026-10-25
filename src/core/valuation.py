"""Institutional Valuation Models:
- Damodaran Free Cash Flow to Firm (FCFF) with exact unrounded floating-point discounting
- Reverse DCF numerical consistency solver with root-bounding guards
- Banking Dividend Discount Model (DDM) with regulatory capital retention
- Enterprise-to-Equity Value bridge
"""
from typing import Dict, Any, List, Optional


class ValuationModelError(Exception):
    """Raised when valuation inputs violate economic or mathematical bounds."""
    pass


class ValuationEngine:
    def calculate_fcff_dcf(
        self,
        fcff_0: float,
        growth_rates_5yr: List[float],
        wacc: float,
        terminal_growth: float,
        terminal_gdp_cap: float = 0.055,
        is_financial: bool = False
    ) -> Dict[str, Any]:
        """
        Calculates intrinsic Enterprise Value using Damodaran FCFF Discounted Cash Flow model.
        Strictly disallowed for Financial Institutions.
        Enforces mathematical bounds:
        - wacc > 0
        - terminal_growth < wacc
        - terminal_growth <= terminal_gdp_cap
        """
        if is_financial:
            raise ValuationModelError("FCFF DCF model cannot be applied to Banks or NBFCs. Use Banking DDM.")

        if wacc <= 0:
            raise ValuationModelError("WACC must be strictly positive.")

        if terminal_growth >= wacc:
            raise ValuationModelError(f"Terminal growth ({terminal_growth:.1%}) cannot be greater than or equal to WACC ({wacc:.1%}).")

        if terminal_growth > terminal_gdp_cap:
            raise ValuationModelError(f"Terminal growth ({terminal_growth:.1%}) exceeds long-term GDP growth cap ({terminal_gdp_cap:.1%}).")

        if len(growth_rates_5yr) != 5:
            raise ValuationModelError("5-year discrete growth projection required.")

        # Annual projected cash flows & present values (unrounded precision)
        cash_flows = []
        discount_factors = []
        pv_cash_flows = []

        current_fcff = fcff_0
        for t, g in enumerate(growth_rates_5yr, start=1):
            current_fcff = current_fcff * (1.0 + g)
            df = 1.0 / ((1.0 + wacc) ** t)
            pv = current_fcff * df

            cash_flows.append(current_fcff)
            discount_factors.append(df)
            pv_cash_flows.append(pv)

        sum_pv_discrete = sum(pv_cash_flows)

        # Terminal value calculation
        fcff_6 = current_fcff * (1.0 + terminal_growth)
        terminal_value_5 = fcff_6 / (wacc - terminal_growth)
        pv_terminal_value = terminal_value_5 / ((1.0 + wacc) ** 5)

        enterprise_value = sum_pv_discrete + pv_terminal_value

        return {
            "fcff_projections": cash_flows,
            "discount_factors": discount_factors,
            "pv_projections": pv_cash_flows,
            "sum_pv_discrete": sum_pv_discrete,
            "terminal_value_year5": terminal_value_5,
            "pv_terminal_value": pv_terminal_value,
            "enterprise_value": enterprise_value
        }

    def solve_reverse_dcf(
        self,
        target_enterprise_value: float,
        fcff_0: float,
        wacc: float,
        terminal_growth: float,
        projection_years: int = 5,
        lower_growth: float = -0.10,
        upper_growth: float = 0.50,
        tolerance: float = 0.01,
        max_iterations: int = 100
    ) -> float:
        """
        Solves for the implied discrete growth rate g* such that DCF(g*) == target_enterprise_value.
        Note: Passing a round-trip verifies Solver Numerical Consistency, not market forecasting truth.
        """
        if target_enterprise_value <= 0:
            raise ValuationModelError("Target Enterprise Value must be positive.")

        def evaluate(g: float) -> float:
            rates = [g] * projection_years
            res = self.calculate_fcff_dcf(fcff_0, rates, wacc, terminal_growth)
            return res["enterprise_value"]

        f_low = evaluate(lower_growth) - target_enterprise_value
        f_high = evaluate(upper_growth) - target_enterprise_value

        if f_low * f_high > 0:
            raise ValuationModelError(f"No implied growth root exists within search range [{lower_growth:.1%}, {upper_growth:.1%}].")

        low, high = lower_growth, upper_growth
        for _ in range(max_iterations):
            mid = (low + high) / 2.0
            f_mid = evaluate(mid) - target_enterprise_value

            if abs(f_mid) <= tolerance:
                return round(mid, 6)

            if f_low * f_mid < 0:
                high = mid
                f_high = f_mid
            else:
                low = mid
                f_low = f_mid

        return round((low + high) / 2.0, 6)

    def calculate_banking_ddm(
        self,
        net_income_0: float,
        return_on_equity: float,
        sustainable_growth: float,
        cost_of_equity: float,
        gdp_cap: float = 0.055
    ) -> Dict[str, Any]:
        """
        Dividend Discount Model for Banks & Financial Institutions.
        Net income is NEVER used as direct dividend proxy.
        Instead, models regulatory capital retention:
        Retention ratio b = g / ROE
        Dividend payout ratio = 1 - b
        D1 = Net Income * (1 - b) * (1 + g)
        Fair Equity Value = D1 / (k_e - g)
        """
        if return_on_equity <= 0:
            raise ValuationModelError("Return on Equity must be positive for DDM.")
        if cost_of_equity <= sustainable_growth:
            raise ValuationModelError("Cost of Equity must be strictly greater than sustainable growth.")
        if sustainable_growth > gdp_cap:
            raise ValuationModelError(f"Growth ({sustainable_growth:.1%}) exceeds GDP cap ({gdp_cap:.1%}).")

        retention_ratio = sustainable_growth / return_on_equity
        if retention_ratio >= 1.0:
            raise ValuationModelError("Retention ratio >= 100% leaves zero dividend payout.")

        payout_ratio = 1.0 - retention_ratio
        expected_dividend_1 = net_income_0 * (1.0 + sustainable_growth) * payout_ratio
        fair_equity_value = expected_dividend_1 / (cost_of_equity - sustainable_growth)

        return {
            "retention_ratio": round(retention_ratio, 4),
            "payout_ratio": round(payout_ratio, 4),
            "expected_dividend_1": round(expected_dividend_1, 2),
            "fair_equity_value": round(fair_equity_value, 2)
        }

    def bridge_enterprise_to_equity_value(
        self,
        enterprise_value: float,
        total_debt: float,
        cash_and_equivalents: float,
        minority_interest: float = 0.0,
        shares_outstanding: Optional[float] = None
    ) -> Dict[str, float]:
        """Calculates Equity Value from Enterprise Value and implied per-share value."""
        equity_value = enterprise_value - total_debt + cash_and_equivalents - minority_interest
        per_share = None
        if shares_outstanding and shares_outstanding > 0:
            per_share = round(equity_value / shares_outstanding, 2)

        return {
            "enterprise_value": round(enterprise_value, 2),
            "total_debt": round(total_debt, 2),
            "cash_and_equivalents": round(cash_and_equivalents, 2),
            "minority_interest": round(minority_interest, 2),
            "equity_value": round(equity_value, 2),
            "implied_per_share": per_share
        }
