"""Corporate Actions Price Adjustment Engine.
Preserves raw prices immutable and derives split/bonus/rights adjusted price and volume series.
"""
from datetime import date
from typing import Dict, List, Tuple
import pandas as pd


class PriceAdjustmentEngine:
    def calculate_adjusted_series(
        self,
        raw_prices: List[Dict[str, any]],
        corporate_actions: List[Dict[str, any]]
    ) -> pd.DataFrame:
        """
        Given a list of daily raw prices and corporate action records:
        Applies backward cumulative adjustment factor F(t) = Product(f_i for ex_date_i > t).
        Returns DataFrame with ['trade_date', 'close_raw', 'volume_raw', 'adj_factor', 'close_adj', 'volume_adj'].
        """
        if not raw_prices:
            return pd.DataFrame()

        df = pd.DataFrame(raw_prices).sort_values("trade_date").reset_index(drop=True)
        
        # Filter actions that adjust prices: split, bonus, rights
        price_actions = [
            ca for ca in corporate_actions
            if ca["action_type"] in ("split", "bonus", "rights") and ca.get("adj_factor") is not None
        ]
        price_actions.sort(key=lambda x: x["ex_date"])

        # Calculate cumulative factor for each date
        factors = []
        for t in df["trade_date"]:
            factor_t = 1.0
            for action in price_actions:
                ex_d = action["ex_date"]
                if isinstance(ex_d, str):
                    ex_d = date.fromisoformat(ex_d)
                if isinstance(t, str):
                    t = date.fromisoformat(t)

                if ex_d > t:
                    factor_t *= action["adj_factor"]
            factors.append(factor_t)

        df["adj_factor"] = factors
        df["close_adj"] = df["close_raw"] * df["adj_factor"]
        df["volume_adj"] = df["volume_raw"] / df["adj_factor"]
        return df
