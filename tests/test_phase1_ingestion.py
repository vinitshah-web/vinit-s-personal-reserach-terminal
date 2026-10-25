"""Tests for Phase 1: Raw Bhavcopy ingestion, hashing, and parsing."""
import pytest
from datetime import date
from pathlib import Path
from src.ingestion.bhavcopy import BhavcopyIngester


def test_bhavcopy_hash_and_storage(tmp_path):
    ingester = BhavcopyIngester(raw_storage_dir=tmp_path)
    sample_content = b"TEST,DATA,CONTENT,12345"
    file_path, file_hash = ingester.store_raw_file("test_bhav.csv", sample_content)

    assert file_path.exists()
    assert len(file_hash) == 64  # SHA-256 hex length
    assert ingester.compute_sha256(sample_content) == file_hash


def test_bhavcopy_parsing_standardization():
    fixture_path = Path(__file__).parent / "fixtures" / "sample_bhavcopy.csv"
    with open(fixture_path, "rb") as f:
        csv_bytes = f.read()

    ingester = BhavcopyIngester()
    file_hash = ingester.compute_sha256(csv_bytes)
    records = ingester.parse_bhavcopy_csv(
        csv_bytes=csv_bytes,
        source_filename="sample_bhavcopy.csv",
        file_hash=file_hash,
        trade_date=date(2024, 1, 5)
    )

    assert len(records) > 0
    # Confirm series filtering (EQ, BE, SM included; others excluded)
    series_set = {r["series"] for r in records}
    assert "EQ" in series_set
    assert "BE" in series_set

    # Verify reliance row
    rel = next(r for r in records if r["ticker"] == "RELIANCE")
    assert rel["isin"] == "INE002A01018"
    assert rel["close_raw"] == 2840.0
    assert rel["volume_raw"] == 1500000
    assert rel["file_hash"] == file_hash
