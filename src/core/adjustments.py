"""Corporate Actions Price Adjustment Engine.
Preserves raw prices immutable and derives split/bonus/rights adjusted price and volume series.
"""
from datetime import date
from typing import Dict, List, Tuple, Union, Any
import pandas as pd


class PriceAdjustmentEngine:
    def calculate_adjusted_series(
        self,
        raw_prices: Union[List[Dict[str, Any]], pd.DataFrame],
        corporate_actions: Union[List[Dict[str, Any]], pd.DataFrame]
    ) -> pd.DataFrame:
        """
        Given daily raw prices and corporate action records:
        Applies backward cumulative adjustment factor F(t) = Product(f_i for ex_date_i > t).
        Returns DataFrame with ['trade_date', 'close_raw', 'volume_raw', 'adj_factor', 'close_adj', 'volume_adj'].
        """
        if isinstance(raw_prices, pd.DataFrame):
            if raw_prices.empty:
                return pd.DataFrame()
            df = raw_prices.copy().sort_values("trade_date").reset_index(drop=True)
        else:
            if not raw_prices:
                return pd.DataFrame()
            df = pd.DataFrame(raw_prices).sort_values("trade_date").reset_index(drop=True)

        if isinstance(corporate_actions, pd.DataFrame):
            ca_list = corporate_actions.to_dict("records")
        else:
            ca_list = list(corporate_actions)

        # Filter actions that adjust prices: split, bonus, rights
        price_actions = []
        for ca in ca_list:
            act_type = str(ca.get("action_type", "")).lower()
            if act_type in ("split", "bonus", "rights"):
                factor = ca.get("adj_factor")
                if factor is None:
                    num = ca.get("ratio_num") if ca.get("ratio_num") is not None else ca.get("ratio_numerator")
                    den = ca.get("ratio_den") if ca.get("ratio_den") is not None else ca.get("ratio_denominator")
                    if act_type == "split" and num and den:
                        factor = float(den) / float(num)
                    elif act_type == "bonus" and num and den:
                        factor = float(den) / float(den + num)
                if factor is not None:
                    ca_copy = dict(ca)
                    ca_copy["adj_factor"] = factor
                    price_actions.append(ca_copy)

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
