"""Bhavcopy Ingestion with cryptographic hashing and schema standardization."""
import hashlib
import io
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple
import pandas as pd


class BhavcopyIngester:
    def __init__(self, raw_storage_dir: Path = None):
        if raw_storage_dir is None:
            self.raw_storage_dir = Path(__file__).parent.parent.parent / "data" / "raw" / "bhavcopy"
        else:
            self.raw_storage_dir = Path(raw_storage_dir)
        self.raw_storage_dir.mkdir(parents=True, exist_ok=True)

    def compute_sha256(self, content_bytes: bytes) -> str:
        """Calculates SHA-256 hash of raw file content."""
        hasher = hashlib.sha256()
        hasher.update(content_bytes)
        return hasher.hexdigest()

    def store_raw_file(self, filename: str, content_bytes: bytes) -> Tuple[Path, str]:
        """Stores immutable raw file into lake and returns (path, sha256_hash)."""
        file_hash = self.compute_sha256(content_bytes)
        target_path = self.raw_storage_dir / filename
        with open(target_path, "wb") as f:
            f.write(content_bytes)
        return target_path, file_hash

    def parse_bhavcopy_csv(
        self,
        csv_bytes: bytes,
        source_filename: str,
        file_hash: str,
        trade_date: date,
        allowed_series: Tuple[str, ...] = ("EQ", "BE", "SM")
    ) -> List[Dict[str, any]]:
        """
        Parses Bhavcopy CSV bytes handling both modern and legacy column headers:
        Standard modern: [SYMBOL, SERIES, OPEN, HIGH, LOW, CLOSE, TOTTRDQTY, ISIN]
        Legacy standard: [SYMBOL, SERIES, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, CLOSE_PRICE, TTL_TRD_QNTY, ISIN]
        """
        df = pd.read_csv(io.BytesIO(csv_bytes))
        df.columns = [c.strip().upper() for c in df.columns]

        # Normalize column names across all 3 historical NSE Bhavcopy generations:
        # 1. Unified format: TckrSymb, SctySrs, OpnPric, HghPric, LwPric, ClsPric, TtlTradgVol, ISIN
        # 2. Modern legacy: SYMBOL, SERIES, OPEN, HIGH, LOW, CLOSE, TOTTRDQTY, ISIN
        # 3. Old legacy PR: SECURITY, SERIES, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, CLOSE_PRICE, NET_TRDQTY
        col_map = {
            "TCKRSYMB": "SYMBOL",
            "SCTYSRS": "SERIES",
            "OPNPRIC": "OPEN",
            "HGHPRIC": "HIGH",
            "LWPRIC": "LOW",
            "CLSPRIC": "CLOSE",
            "TTLTRADGVOL": "TOTTRDQTY",
            "OPEN_PRICE": "OPEN",
            "HIGH_PRICE": "HIGH",
            "LOW_PRICE": "LOW",
            "CLOSE_PRICE": "CLOSE",
            "TTL_TRD_QNTY": "TOTTRDQTY",
            "TOTAL_TRADED_QUANTITY": "TOTTRDQTY",
            "NET_TRDQTY": "TOTTRDQTY",
            "DELIV_PER": "DELIVERY_PCT"
        }
        df = df.rename(columns=col_map)

        required = ["SYMBOL", "SERIES", "CLOSE", "TOTTRDQTY", "ISIN"]
        for col in required:
            if col not in df.columns:
                raise ValueError(f"Required Bhavcopy column '{col}' missing from {source_filename}")

        # Filter by series
        df = df[df["SERIES"].isin(allowed_series)]

        now_utc = datetime.now(timezone.utc)
        records = []
        for _, row in df.iterrows():
            records.append({
                "isin": str(row["ISIN"]).strip(),
                "ticker": str(row["SYMBOL"]).strip(),
                "series": str(row["SERIES"]).strip(),
                "trade_date": trade_date,
                "open_raw": float(row["OPEN"]) if pd.notnull(row.get("OPEN")) else None,
                "high_raw": float(row["HIGH"]) if pd.notnull(row.get("HIGH")) else None,
                "low_raw": float(row["LOW"]) if pd.notnull(row.get("LOW")) else None,
                "close_raw": float(row["CLOSE"]),
                "volume_raw": int(row["TOTTRDQTY"]),
                "delivery_pct": float(row["DELIVERY_PCT"]) if pd.notnull(row.get("DELIVERY_PCT")) else None,
                "source_file": source_filename,
                "file_hash": file_hash,
                "ingested_at": now_utc
            })
        return records
