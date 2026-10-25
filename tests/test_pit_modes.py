"""Acceptance Tests: Point-in-time queries, same-day publication boundaries, restatements, and delisted universe."""
import pytest
from datetime import date, datetime, timezone
from src.db.models import Security, FinancialStatement, FinancialLineItem
from src.core.universe import PointInTimeUniverse, PITMode


def test_same_day_publication_and_cutoff_boundaries(db_session):
    """
    Acceptance Test 2: Same-day publication cutoff boundary.
    Scenario:
    Company discloses earnings after market hours at 18:30 on Day T (2024-08-14).
    A query made as-of market close at 15:30 on Day T must NOT access the disclosure.
    A query made at 19:00 on Day T must access the disclosure in RECONSTRUCTED mode.
    """
    pub_ts = datetime(2024, 8, 14, 18, 30)
    ingest_ts = datetime(2024, 8, 15, 6, 0)

    fs = FinancialStatement(
        isin="INE002A01018",
        period_start=date(2024, 4, 1),
        period_end=date(2024, 6, 30),
        period_type="quarterly",
        consolidated=True,
        currency="INR",
        unit_multiplier=1.0,
        published_at=pub_ts,
        ingested_at=ingest_ts,
        source_url="https://example.com/q1.pdf",
        source_type="xbrl",
        is_restatement=False,
        valid_from=ingest_ts,
        valid_to=None
    )
    db_session.add(fs)
    db_session.commit()

    pit = PointInTimeUniverse(db_session)

    # 1. Query at 15:30 (before disclosure) -> Must return None
    cutoff_market_close = datetime(2024, 8, 14, 15, 30)
    res_early = pit.get_point_in_time_financials(
        isin="INE002A01018",
        cutoff_timestamp=cutoff_market_close,
        mode=PITMode.RECONSTRUCTED
    )
    assert res_early is None, "Disclosure leaked into pre-announcement cutoff time!"

    # 2. Query at 19:00 (after disclosure) -> Must return the filing
    cutoff_evening = datetime(2024, 8, 14, 19, 0)
    res_late = pit.get_point_in_time_financials(
        isin="INE002A01018",
        cutoff_timestamp=cutoff_evening,
        mode=PITMode.RECONSTRUCTED
    )
    assert res_late is not None
    assert res_late.published_at == pub_ts


def test_operational_vs_reconstructed_modes(db_session):
    """
    Acceptance Test 1: Operational (AS_KNOWN) vs Reconstructed (RECONSTRUCTED).
    Filing published at 18:30 on Day T, but downloaded/ingested by batch at 06:00 on Day T+1.
    Query at 20:00 on Day T:
    - AS_KNOWN mode: Returns None (platform had not yet ingested it).
    - RECONSTRUCTED mode: Returns filing (it had been publicly published).
    """
    pub_ts = datetime(2024, 8, 14, 18, 30)
    ingest_ts = datetime(2024, 8, 15, 6, 0)

    fs = FinancialStatement(
        isin="INE040A01034",
        period_start=date(2024, 4, 1),
        period_end=date(2024, 6, 30),
        period_type="quarterly",
        consolidated=True,
        currency="INR",
        unit_multiplier=1.0,
        published_at=pub_ts,
        ingested_at=ingest_ts,
        source_url="https://example.com/hdfc_q1.pdf",
        source_type="xbrl",
        is_restatement=False,
        valid_from=ingest_ts,
        valid_to=None
    )
    db_session.add(fs)
    db_session.commit()

    pit = PointInTimeUniverse(db_session)
    cutoff = datetime(2024, 8, 14, 20, 0)

    # AS_KNOWN mode -> Not yet known to platform at Day T 20:00
    as_known_res = pit.get_point_in_time_financials(
        isin="INE040A01034",
        cutoff_timestamp=cutoff,
        mode=PITMode.AS_KNOWN
    )
    assert as_known_res is None

    # RECONSTRUCTED mode -> Published at 18:30, so available to market
    recon_res = pit.get_point_in_time_financials(
        isin="INE040A01034",
        cutoff_timestamp=cutoff,
        mode=PITMode.RECONSTRUCTED
    )
    assert recon_res is not None
    assert recon_res.isin == "INE040A01034"


def test_restatement_version_preservation(db_session):
    """
    Acceptance Test 3: Restatement version preservation.
    Original Q1 filed Aug 15. Restated Q1 filed Nov 20.
    Query as-of Oct 1 returns original version.
    Query as-of Dec 1 returns restated version.
    """
    orig_pub = datetime(2024, 8, 14, 18, 30)
    orig_ingest = datetime(2024, 8, 15, 6, 0)
    restated_ts = datetime(2024, 11, 20, 14, 0)

    orig = FinancialStatement(
        isin="INE002A01018",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 3, 31),
        period_type="annual",
        consolidated=True,
        currency="INR",
        unit_multiplier=1.0,
        published_at=orig_pub,
        ingested_at=orig_ingest,
        source_url="https://example.com/orig_annual.pdf",
        source_type="xbrl",
        is_restatement=False,
        valid_from=orig_ingest,
        valid_to=restated_ts,
        restated_at=restated_ts
    )
    db_session.add(orig)
    db_session.commit()

    # Insert restated row
    restated = FinancialStatement(
        isin="INE002A01018",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 3, 31),
        period_type="annual",
        consolidated=True,
        currency="INR",
        unit_multiplier=1.0,
        published_at=restated_ts,
        ingested_at=restated_ts,
        source_url="https://example.com/restated_annual.pdf",
        source_type="xbrl",
        is_restatement=True,
        supersedes_id=orig.id,
        valid_from=restated_ts,
        valid_to=None
    )
    db_session.add(restated)
    db_session.commit()

    pit = PointInTimeUniverse(db_session)

    # Query at Oct 1 (pre-restatement) -> Returns original
    cutoff_oct = datetime(2024, 10, 1, 0, 0)
    res_oct = pit.get_point_in_time_financials("INE002A01018", cutoff_oct, as_of_period_end=date(2024, 3, 31), mode=PITMode.AS_KNOWN)
    assert res_oct is not None
    assert res_oct.id == orig.id
    assert res_oct.is_restatement is False

    # Query at Dec 1 (post-restatement) -> Returns restated
    cutoff_dec = datetime(2024, 12, 1, 0, 0)
    res_dec = pit.get_point_in_time_financials("INE002A01018", cutoff_dec, as_of_period_end=date(2024, 3, 31), mode=PITMode.AS_KNOWN)
    assert res_dec is not None
    assert res_dec.id == restated.id
    assert res_dec.is_restatement is True


def test_historical_universe_and_delisted_stocks(db_session):
    """
    Acceptance Test 4: Historical Universe & Delisted Stock Handling.
    Kingfisher Airlines (KFA) was listed in 2006 and delisted on 2014-12-01.
    Query at 2012-01-01 must include KFA.
    Query at 2015-01-01 must EXCLUDE KFA.
    """
    pit = PointInTimeUniverse(db_session)

    # In 2012: KFA was actively trading
    univ_2012 = pit.get_tradable_universe(as_of_date=date(2012, 1, 1))
    tickers_2012 = {s.ticker_current for s in univ_2012}
    assert "KFA" in tickers_2012
    assert "RELIANCE" in tickers_2012

    # In 2015: KFA is delisted
    univ_2015 = pit.get_tradable_universe(as_of_date=date(2015, 1, 1))
    tickers_2015 = {s.ticker_current for s in univ_2015}
    assert "KFA" not in tickers_2015
    assert "RELIANCE" in tickers_2015
