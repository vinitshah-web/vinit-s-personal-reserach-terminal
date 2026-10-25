"""Acceptance tests for Phase 2: Universe Master and Index Constituent History.
Tests point-in-time constituent membership, survivorship-free queries,
series filtering (rejecting SME/bonds), and real NSE index ingestion.
"""
from datetime import date, datetime
import os
import pytest
from sqlalchemy.orm import Session
from src.db.models import Security, IndexConstituent, IndexPrice
from src.core.universe import PointInTimeUniverse
from src.ingestion.index_parser import IndexDataIngester


def test_point_in_time_index_constituents_survivorship(db_session: Session):
    """
    Test that historical index constituent lookups eliminate survivorship bias:
    Stock A was a Nifty 50 constituent from 2018-01-01 to 2022-06-30.
    Stock B was added to Nifty 50 on 2021-01-01 and is still active.
    Stock C was added to Nifty 50 on 2023-01-01.
    """
    sec_a = Security(isin="INE001A01010", ticker_current="STKA", company_name="Stock A Ltd", listing_date=date(2015, 1, 1), series="EQ")
    sec_b = Security(isin="INE002B01020", ticker_current="STKB", company_name="Stock B Ltd", listing_date=date(2017, 1, 1), series="EQ")
    sec_c = Security(isin="INE003C01030", ticker_current="STKC", company_name="Stock C Ltd", listing_date=date(2020, 1, 1), series="EQ")
    db_session.add_all([sec_a, sec_b, sec_c])
    db_session.commit()

    # Index memberships
    ic_a = IndexConstituent(index_name="NIFTY 50", isin="INE001A01010", inclusion_date=date(2018, 1, 1), exclusion_date=date(2022, 6, 30))
    ic_b = IndexConstituent(index_name="NIFTY 50", isin="INE002B01020", inclusion_date=date(2021, 1, 1), exclusion_date=None)
    ic_c = IndexConstituent(index_name="NIFTY 50", isin="INE003C01030", inclusion_date=date(2023, 1, 1), exclusion_date=None)
    db_session.add_all([ic_a, ic_b, ic_c])
    db_session.commit()

    pit_universe = PointInTimeUniverse(db_session)

    # 1. As of 2017-12-31 (Before any were in Nifty 50)
    constituents_2017 = pit_universe.get_index_constituents("NIFTY 50", date(2017, 12, 31))
    assert constituents_2017 == []

    # 2. As of 2019-06-01 (Only Stock A was in Nifty 50)
    constituents_2019 = pit_universe.get_index_constituents("NIFTY 50", date(2019, 6, 1))
    assert constituents_2019 == ["INE001A01010"]

    # 3. As of 2021-06-01 (Stock A and Stock B were in Nifty 50, but not Stock C)
    constituents_2021 = pit_universe.get_index_constituents("NIFTY 50", date(2021, 6, 1))
    assert set(constituents_2021) == {"INE001A01010", "INE002B01020"}

    # 4. As of 2024-01-01 (Stock A excluded; Stock B and Stock C active)
    constituents_2024 = pit_universe.get_index_constituents("NIFTY 50", date(2024, 1, 1))
    assert set(constituents_2024) == {"INE002B01020", "INE003C01030"}
    assert "INE001A01010" not in constituents_2024


def test_index_constituent_series_filtering(db_session: Session):
    """
    Test that SME instruments (series 'SM') and bonds ('GB') are strictly rejected
    even if erroneously recorded under index constituents.
    """
    sec_eq = Security(isin="INE100A01011", ticker_current="MAIN", company_name="Main EQ Ltd", listing_date=date(2020, 1, 1), series="EQ")
    sec_sme = Security(isin="INE200B01012", ticker_current="SMES", company_name="SME Firm Ltd", listing_date=date(2020, 1, 1), series="SM")
    sec_bond = Security(isin="IN0020200010", ticker_current="GS2030", company_name="Govt Bond 2030", listing_date=date(2020, 1, 1), series="GB")
    db_session.add_all([sec_eq, sec_sme, sec_bond])
    db_session.commit()

    db_session.add_all([
        IndexConstituent(index_name="BROAD_INDEX", isin="INE100A01011", inclusion_date=date(2020, 1, 1)),
        IndexConstituent(index_name="BROAD_INDEX", isin="INE200B01012", inclusion_date=date(2020, 1, 1)),
        IndexConstituent(index_name="BROAD_INDEX", isin="IN0020200010", inclusion_date=date(2020, 1, 1)),
    ])
    db_session.commit()

    pit = PointInTimeUniverse(db_session)
    constituents = pit.get_index_constituents("BROAD_INDEX", date(2021, 1, 1), allowed_series=["EQ", "BE"])
    assert constituents == ["INE100A01011"]


def test_real_nifty50_index_csv_ingestion(db_session: Session):
    """
    Tests ingestion of actual NIFTY 50 historical CSV file from workspace root.
    """
    csv_path = "NIFTY 50-25-10-2025-to-25-10-2026.csv"
    assert os.path.exists(csv_path), "Workspace NIFTY 50 CSV file must exist"

    ingester = IndexDataIngester(db_session)
    count = ingester.ingest_csv(csv_path, index_name="NIFTY 50")
    assert count > 200, f"Expected > 200 trading days ingested, got {count}"

    # Verify latest trading day in file (23-OCT-2026)
    rec_latest = db_session.query(IndexPrice).filter(
        IndexPrice.index_name == "NIFTY 50",
        IndexPrice.trade_date == date(2026, 10, 23)
    ).first()

    assert rec_latest is not None
    assert rec_latest.open == 22742.2
    assert rec_latest.high == 22787.25
    assert rec_latest.low == 22372.0
    assert rec_latest.close == 22600.0
    assert rec_latest.volume == 364190826
    assert rec_latest.turnover_cr == 29859.76

    # Test idempotency (re-ingestion should not duplicate or error)
    reingest_count = ingester.ingest_csv(csv_path, index_name="NIFTY 50")
    assert reingest_count == 0  # Updated existing records, 0 new
