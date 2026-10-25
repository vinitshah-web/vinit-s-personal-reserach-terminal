"""NSE Index historical price data ingester.
Parses official NSE Index CSV files (e.g. NIFTY 50, NIFTY 500) and persists them to index_price table.
"""
from datetime import datetime, date
import pandas as pd
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from src.db.models import IndexPrice


class IndexDataIngester:
    def __init__(self, session: Session):
        self.session = session

    def ingest_csv(self, file_path: str, index_name: str = "NIFTY 50") -> int:
        """
        Parses official NSE Index CSV with headers like:
        Date ,Open ,High ,Low ,Close ,Shares Traded ,Turnover (₹ Cr)
        """
        df = pd.read_csv(file_path)
        df.columns = [c.strip() for c in df.columns]

        # Normalize column mapping
        col_map = {
            "Date": "trade_date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Shares Traded": "volume",
            "Turnover (₹ Cr)": "turnover_cr"
        }
        df = df.rename(columns=col_map)

        records_count = 0
        for _, row in df.iterrows():
            # Date format typically 23-OCT-2026 or DD-MMM-YYYY
            raw_date = str(row["trade_date"]).strip()
            trade_dt = datetime.strptime(raw_date, "%d-%b-%Y").date()

            def _to_float(val):
                if pd.isna(val) or val == "-" or val == "":
                    return None
                try:
                    return float(str(val).replace(",", "").strip())
                except ValueError:
                    return None

            def _to_int(val):
                if pd.isna(val) or val == "-" or val == "":
                    return None
                try:
                    return int(float(str(val).replace(",", "").strip()))
                except ValueError:
                    return None

            # Check if record already exists
            existing = self.session.query(IndexPrice).filter(
                IndexPrice.index_name == index_name,
                IndexPrice.trade_date == trade_dt
            ).first()

            if not existing:
                idx_record = IndexPrice(
                    index_name=index_name,
                    trade_date=trade_dt,
                    open=_to_float(row.get("open")),
                    high=_to_float(row.get("high")),
                    low=_to_float(row.get("low")),
                    close=_to_float(row.get("close")),
                    volume=_to_int(row.get("volume")),
                    turnover_cr=_to_float(row.get("turnover_cr"))
                )
                self.session.add(idx_record)
                records_count += 1
            else:
                existing.open = _to_float(row.get("open"))
                existing.high = _to_float(row.get("high"))
                existing.low = _to_float(row.get("low"))
                existing.close = _to_float(row.get("close"))
                existing.volume = _to_int(row.get("volume"))
                existing.turnover_cr = _to_float(row.get("turnover_cr"))

        self.session.commit()
        return records_count
