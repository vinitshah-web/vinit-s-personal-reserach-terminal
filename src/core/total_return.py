"""Total Return Index Engine with Dividend Reinvestment."""
from datetime import date
from typing import Dict, List, Optional
import pandas as pd


class TotalReturnEngine:
    def calculate_total_return_series(
        self,
        adjusted_price_df: pd.DataFrame,
        corporate_actions: List[Dict[str, any]],
        base_index: float = 10000.0
    ) -> pd.DataFrame:
        """
        Calculates cumulative Total Return (TR) index.
        Convention:
        - Dividends are adjusted to historical share basis: D_adj(d) = D_raw(d) * F(d).
        - Cash dividends are reinvested at the ex-date close price (close_adj).
        - TR(d) = TR(d-1) * [close_adj(d) + D_adj(d)] / close_adj(d-1) on ex-dates.
        - TR(d) = TR(d-1) * [close_adj(d)] / close_adj(d-1) on non-dividend dates.
        """
        if adjusted_price_df.empty:
            return pd.DataFrame()

        df = adjusted_price_df.sort_values("trade_date").reset_index(drop=True).copy()

        # Build dividend map: ex_date -> D_raw
        div_map = {}
        for ca in corporate_actions:
            if "dividend" in ca["action_type"] and ca.get("dividend_per_share") is not None:
                ex_d = ca["ex_date"]
                if isinstance(ex_d, str):
                    ex_d = date.fromisoformat(ex_d)
                div_map[ex_d] = float(ca["dividend_per_share"])

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

            period_multiplier = (curr_close + adj_div) / prev_close
            curr_tr = tr_values[-1] * period_multiplier
            tr_values.append(curr_tr)

        df["dividend_adj"] = adj_dividends
        df["total_return_index"] = tr_values
        return df
