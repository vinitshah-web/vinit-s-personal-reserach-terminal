"""Corporate Actions Ingestion and Adjustment Factor Derivation."""
import json
import re
import io
import pandas as pd
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional


class CorporateActionParser:
    def compute_split_factor(self, ratio_new: int, ratio_old: int = 1) -> float:
        """
        Split ratio new:old (e.g., 5:1 means each 1 old share becomes 5 new shares).
        Adjustment factor f = old / new = 1 / 5 = 0.20.
        """
        if ratio_new <= 0 or ratio_old <= 0:
            raise ValueError(f"Invalid split ratio: {ratio_new}:{ratio_old}")
        return ratio_old / ratio_new

    def compute_bonus_factor(self, bonus_shares: int, existing_shares: int) -> float:
        """
        Bonus ratio b:e (e.g., 1:2 means 1 bonus share for every 2 held).
        Total shares become e + b.
        Adjustment factor f = e / (e + b) = 2 / (2 + 1) = 2/3.
        """
        if bonus_shares <= 0 or existing_shares <= 0:
            raise ValueError(f"Invalid bonus ratio: {bonus_shares}:{existing_shares}")
        return existing_shares / (existing_shares + bonus_shares)

    def compute_rights_terp_factor(
        self,
        cum_rights_price: float,
        subscription_price: float,
        new_shares: int,
        old_shares: int
    ) -> float:
        """
        Theoretical Ex-Rights Price (TERP) calculation:
        TERP = (cum_price * old_shares + sub_price * new_shares) / (old_shares + new_shares)
        Factor f = TERP / cum_price
        """
        if cum_rights_price <= 0:
            raise ValueError("Cum-rights price must be strictly positive.")
        if new_shares <= 0 or old_shares <= 0:
            raise ValueError(f"Invalid rights entitlement ratio: {new_shares}:{old_shares}")

        total_shares = old_shares + new_shares
        terp = (cum_rights_price * old_shares + subscription_price * new_shares) / total_shares
        return round(terp / cum_rights_price, 6)

    def parse_corporate_actions_feed(self, raw_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parses raw corporate action feed entries into standardized database records."""
        parsed = []
        for ev in raw_events:
            action_type = ev["action_type"].lower().strip()
            num = ev.get("ratio_numerator")
            den = ev.get("ratio_denominator", 1)
            adj_factor = None

            if action_type == "split":
                adj_factor = self.compute_split_factor(num, den)
            elif action_type == "bonus":
                adj_factor = self.compute_bonus_factor(num, den)
            elif action_type == "rights":
                cum_p = ev.get("cum_rights_price")
                sub_p = ev.get("subscription_price")
                if cum_p is not None and sub_p is not None:
                    adj_factor = self.compute_rights_terp_factor(cum_p, sub_p, num, den)

            pub_ts = datetime.fromisoformat(ev["published_at"])
            ingest_ts = datetime.now(timezone.utc)

            parsed.append({
                "isin": ev["isin"].strip(),
                "ex_date": date.fromisoformat(ev["ex_date"]),
                "record_date": date.fromisoformat(ev["record_date"]) if ev.get("record_date") else None,
                "action_type": action_type,
                "ratio_numerator": num,
                "ratio_denominator": den,
                "dividend_per_share": float(ev["dividend_per_share"]) if ev.get("dividend_per_share") is not None else None,
                "dividend_type": ev.get("dividend_type"),
                "subscription_price": float(ev["subscription_price"]) if ev.get("subscription_price") is not None else None,
                "details_json": json.dumps(ev.get("details", {})),
                "source_url": ev["source_url"],
                "published_at": pub_ts,
                "ingested_at": ingest_ts,
                "effective_from": date.fromisoformat(ev["ex_date"]),
                "effective_to": None,
                "adj_factor": adj_factor
            })
        return parsed

    def parse_nse_bc_csv(
        self,
        csv_text: str,
        symbol_to_isin_map: Dict[str, str],
        source_url: str = "https://nseindia.com/reports/PR231026/bc23102026.csv",
        published_at: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Parses official NSE Book Closure / Corporate Actions CSV (bc<DDMMYYYY>.csv)."""
        df = pd.read_csv(io.StringIO(csv_text), skipinitialspace=True)
        df.columns = [c.strip().upper() for c in df.columns]

        # Only process primary equity series to avoid duplicate corporate actions
        if "SERIES" in df.columns:
            df = df[df["SERIES"].isin(["EQ", "BE"])]

        if published_at is None:
            published_at = datetime.now(timezone.utc)
        ingested_at = datetime.now(timezone.utc)

        parsed = []
        seen = set()

        for _, row in df.iterrows():
            sym = str(row.get("SYMBOL", "")).strip()
            if not sym or sym not in symbol_to_isin_map:
                continue

            isin = symbol_to_isin_map[sym]
            purpose = str(row.get("PURPOSE", "")).strip()
            ex_date_str = str(row.get("EX_DT", "")).strip()
            rec_date_str = str(row.get("RECORD_DT", "")).strip()

            try:
                ex_dt = date.fromisoformat(ex_date_str)
            except Exception:
                continue

            try:
                rec_dt = date.fromisoformat(rec_date_str) if rec_date_str and rec_date_str != "nan" else None
            except Exception:
                rec_dt = None

            # 1. Dividend
            m_div = re.search(r'INTDIV\s*-\s*R[SE]\s*([0-9.]+)\s*PER\s*SH', purpose, re.IGNORECASE)
            if m_div:
                d_val = float(m_div.group(1))
                key = (isin, ex_dt, "dividend")
                if key not in seen:
                    seen.add(key)
                    parsed.append({
                        "isin": isin,
                        "ex_date": ex_dt,
                        "record_date": rec_dt,
                        "action_type": "dividend",
                        "ratio_numerator": None,
                        "ratio_denominator": None,
                        "dividend_per_share": d_val,
                        "dividend_type": "INTERIM",
                        "subscription_price": None,
                        "details_json": json.dumps({"raw_purpose": purpose, "symbol": sym}),
                        "source_url": source_url,
                        "published_at": published_at,
                        "ingested_at": ingested_at,
                        "effective_from": ex_dt,
                        "effective_to": None,
                        "adj_factor": None
                    })

            # 2. Split
            m_splt = re.search(r'FVSPLT\s*FRM\s*RS\s*([0-9.]+)\s*TO\s*RS\s*([0-9.]+)', purpose, re.IGNORECASE)
            if m_splt:
                old_fv = float(m_splt.group(1))
                new_fv = float(m_splt.group(2))
                if new_fv > 0:
                    split_mult = int(round(old_fv / new_fv))
                    key = (isin, ex_dt, "split")
                    if key not in seen:
                        seen.add(key)
                        adj_factor = self.compute_split_factor(split_mult, 1)
                        parsed.append({
                            "isin": isin,
                            "ex_date": ex_dt,
                            "record_date": rec_dt,
                            "action_type": "split",
                            "ratio_numerator": split_mult,
                            "ratio_denominator": 1,
                            "dividend_per_share": None,
                            "dividend_type": None,
                            "subscription_price": None,
                            "details_json": json.dumps({"raw_purpose": purpose, "old_fv": old_fv, "new_fv": new_fv, "symbol": sym}),
                            "source_url": source_url,
                            "published_at": published_at,
                            "ingested_at": ingested_at,
                            "effective_from": ex_dt,
                            "effective_to": None,
                            "adj_factor": adj_factor
                        })

            # 3. Bonus
            m_bonus = re.search(r'BONUS\s*([0-9]+):([0-9]+)', purpose, re.IGNORECASE)
            if m_bonus:
                b_num = int(m_bonus.group(1))
                b_den = int(m_bonus.group(2))
                key = (isin, ex_dt, "bonus")
                if key not in seen:
                    seen.add(key)
                    adj_factor = self.compute_bonus_factor(b_num, b_den)
                    parsed.append({
                        "isin": isin,
                        "ex_date": ex_dt,
                        "record_date": rec_dt,
                        "action_type": "bonus",
                        "ratio_numerator": b_num,
                        "ratio_denominator": b_den,
                        "dividend_per_share": None,
                        "dividend_type": None,
                        "subscription_price": None,
                        "details_json": json.dumps({"raw_purpose": purpose, "symbol": sym}),
                        "source_url": source_url,
                        "published_at": published_at,
                        "ingested_at": ingested_at,
                        "effective_from": ex_dt,
                        "effective_to": None,
                        "adj_factor": adj_factor
                    })

        return parsed
