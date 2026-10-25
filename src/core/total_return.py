"""Total Return Index Engine with Dividend Reinvestment & Rights Issue Strategies."""
from datetime import date
from enum import Enum
from typing import Dict, List, Optional
import pandas as pd


class RightsStrategy(str, Enum):
    SUBSCRIBE = "subscribe"
    SELL_RENOUNCE = "sell_renounce"
    LAPSE = "lapse"


class IncompleteRightsDataError(Exception):
    """Raised when required rights issue parameters are missing."""
    pass


class TotalReturnEngine:
    def calculate_total_return_series(
        self,
        adjusted_price_df: pd.DataFrame,
        corporate_actions: List[Dict[str, any]],
        base_index: float = 10000.0,
        rights_strategy: RightsStrategy = RightsStrategy.SUBSCRIBE
    ) -> pd.DataFrame:
        """
        Calculates cumulative Total Return (TR) index across dividends and corporate actions.
        Convention:
        - Dividends: D_adj(d) = D_raw(d) * F(d). Reinvested on ex-date at close_adj.
        - Rights Issues:
          * SUBSCRIBE: Investor exercises entitlement. Portfolio wealth grows with TERP.
          * SELL_RENOUNCE: Investor sells rights entitlement for cash (P_cum - TERP) at ex-date.
          * LAPSE: Investor takes no action. Incurs permanent dilution loss (f_rights - 1).
        """
        if adjusted_price_df.empty:
            return pd.DataFrame()

        df = adjusted_price_df.sort_values("trade_date").reset_index(drop=True).copy()

        # Build corporate action maps
        div_map = {}
        rights_map = {}
        for ca in corporate_actions:
            ex_d = ca["ex_date"]
            if isinstance(ex_d, str):
                ex_d = date.fromisoformat(ex_d)

            action_type = ca["action_type"]
            if "dividend" in action_type and ca.get("dividend_per_share") is not None:
                div_map[ex_d] = float(ca["dividend_per_share"])
            elif action_type == "rights":
                num = ca.get("ratio_numerator")
                den = ca.get("ratio_denominator", 1)
                cum_p = ca.get("cum_rights_price")
                sub_p = ca.get("subscription_price")
                if None in (num, den, cum_p, sub_p):
                    raise IncompleteRightsDataError(f"Rights issue on {ex_d} lacks required terms (numerator, denominator, cum_price, sub_price).")
                
                total_shares = den + num
                terp = (cum_p * den + sub_p * num) / total_shares
                f_rights = terp / cum_p
                rights_map[ex_d] = {
                    "num": num,
                    "den": den,
                    "cum_price": cum_p,
                    "sub_price": sub_p,
                    "terp": terp,
                    "factor": f_rights
                }

        tr_values = [base_index]
        adj_dividends = [0.0]

        for i in range(1, len(df)):
            curr_date = df.loc[i, "trade_date"]
            if isinstance(curr_date, str):
                curr_date = date.fromisoformat(curr_date)

            prev_close = df.loc[i - 1, "close_adj"]
            curr_close = df.loc[i, "close_adj"]
            curr_factor = df.loc[i, "adj_factor"]

            raw_div = div_map.get(curr_date, 0.0)
            adj_div = raw_div * curr_factor
            adj_dividends.append(adj_div)

            # Check if current date is a rights ex-date
            if curr_date in rights_map:
                r_info = rights_map[curr_date]
                if rights_strategy == RightsStrategy.SUBSCRIBE:
                    period_multiplier = (curr_close + adj_div) / prev_close
                elif rights_strategy == RightsStrategy.SELL_RENOUNCE:
                    # Cash received from renunciation added to return
                    renounce_cash_adj = (r_info["cum_price"] - r_info["terp"]) * curr_factor
                    period_multiplier = (curr_close + adj_div + renounce_cash_adj) / prev_close
                elif rights_strategy == RightsStrategy.LAPSE:
                    # Dilution loss: does not receive new shares and does not receive cash
                    period_multiplier = (curr_close + adj_div) / (prev_close / r_info["factor"])
            else:
                period_multiplier = (curr_close + adj_div) / prev_close

            curr_tr = tr_values[-1] * period_multiplier
            tr_values.append(curr_tr)

        df["dividend_adj"] = adj_dividends
        df["total_return_index"] = tr_values
        return df
