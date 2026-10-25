"""Acceptance tests for Phase 3: TTM Flow Aggregator & Point-In-Time Gating.
Verifies exact 4-quarter aggregation, missing-quarter detection, anti-leakage,
and restatement history handling.
"""
from datetime import date, datetime, timezone
import pytest
from sqlalchemy.orm import Session
from src.db.models import Security, FinancialStatement, FinancialLineItem
from src.db.seed_defs import seed_standard_line_items
from src.core.fundamentals.ttm import TTMAggregator, IncompleteTTMDataError


def _setup_quarters(db_session: Session, isin: str):
    seed_standard_line_items(db_session)
    # 4 consecutive quarters for FY24:
    # Q1: period_end 2023-06-30, published 2023-07-20 18:00
    # Q2: period_end 2023-09-30, published 2023-10-22 18:00
    # Q3: period_end 2023-12-31, published 2024-01-25 18:00
    # Q4: period_end 2024-03-31, published 2024-05-15 18:00
    quarters = [
        (date(2023, 4, 1), date(2023, 6, 30), datetime(2023, 7, 20, 18, 0), 100.0, 20.0, 12.0),
        (date(2023, 7, 1), date(2023, 9, 30), datetime(2023, 10, 22, 18, 0), 110.0, 22.0, 14.0),
        (date(2023, 10, 1), date(2023, 12, 31), datetime(2024, 1, 25, 18, 0), 120.0, 25.0, 16.0),
        (date(2024, 1, 1), date(2024, 3, 31), datetime(2024, 5, 15, 18, 0), 130.0, 28.0, 18.0),
    ]

    for p_start, p_end, pub_dt, rev, ebitda, pat in quarters:
        stmt = FinancialStatement(
            isin=isin,
            period_start=p_start,
            period_end=p_end,
            period_type="QUARTERLY",
            consolidated=True,
            currency="INR",
            unit_multiplier=1.0,
            published_at=pub_dt,
            ingested_at=pub_dt,
            valid_from=pub_dt,
            source_url="https://nseindia.com/filings",
            source_type="NSE_XBRL"
        )
        db_session.add(stmt)
        db_session.flush()

        # Add line items
        db_session.add_all([
            FinancialLineItem(statement_id=stmt.id, item_code="REV", value=rev),
            FinancialLineItem(statement_id=stmt.id, item_code="EBITDA", value=ebitda),
            FinancialLineItem(statement_id=stmt.id, item_code="PAT", value=pat),
            FinancialLineItem(statement_id=stmt.id, item_code="TOTAL_DEBT", value=50.0),
            FinancialLineItem(statement_id=stmt.id, item_code="CASH_EQUIV", value=20.0),
        ])
    db_session.commit()


def test_ttm_aggregation_exact_flow_sums(db_session: Session):
    sec = Security(isin="INE009A01019", ticker_current="TESTEQ", company_name="Test Equity Ltd", listing_date=date(2020, 1, 1), series="EQ")
    db_session.add(sec)
    db_session.commit()

    _setup_quarters(db_session, "INE009A01019")

    ttm_agg = TTMAggregator(db_session)

    # Query as of 2024-05-20 (After all 4 quarters published)
    cutoff = datetime(2024, 5, 20, 10, 0)
    ttm = ttm_agg.get_ttm_metrics("INE009A01019", cutoff_timestamp=cutoff)

    # Expected sums:
    # REV: 100 + 110 + 120 + 130 = 460.0
    # EBITDA: 20 + 22 + 25 + 28 = 95.0
    # PAT: 12 + 14 + 16 + 18 = 60.0
    assert ttm["REV"] == 460.0
    assert ttm["EBITDA"] == 95.0
    assert ttm["PAT"] == 60.0
    assert ttm["TOTAL_DEBT"] == 50.0
    assert ttm["CASH_EQUIV"] == 20.0
    assert ttm["quarters_count"] == 4


def test_ttm_fails_closed_before_publication(db_session: Session):
    """
    On 2024-05-15 12:00 (6 hours BEFORE Q4 filing at 18:00),
    only 3 quarters exist. TTMAggregator must fail closed.
    """
    sec = Security(isin="INE010A01010", ticker_current="TESTLEAK", company_name="Test Leak Ltd", listing_date=date(2020, 1, 1), series="EQ")
    db_session.add(sec)
    db_session.commit()

    _setup_quarters(db_session, "INE010A01010")

    ttm_agg = TTMAggregator(db_session)
    cutoff_before_q4 = datetime(2024, 5, 15, 12, 0)

    with pytest.raises(IncompleteTTMDataError) as exc_info:
        ttm_agg.get_ttm_metrics("INE010A01010", cutoff_timestamp=cutoff_before_q4)

    assert "only 3 valid quarters available" in str(exc_info.value)


def test_ttm_restatement_versioning(db_session: Session):
    """
    Q3 PAT was originally 16.0.
    On 2024-07-01, company files restatement adjusting Q3 PAT down to 10.0.
    - Query on 2024-06-01 must see PAT = 60.0 (original 16.0)
    - Query on 2024-07-15 must see PAT = 54.0 (restated 10.0)
    """
    sec = Security(isin="INE011A01011", ticker_current="TESTREST", company_name="Test Restate Ltd", listing_date=date(2020, 1, 1), series="EQ")
    db_session.add(sec)
    db_session.commit()

    _setup_quarters(db_session, "INE011A01011")

    # Find the original Q3 statement
    orig_q3 = db_session.query(FinancialStatement).filter(
        FinancialStatement.isin == "INE011A01011",
        FinancialStatement.period_end == date(2023, 12, 31)
    ).first()

    # Create restatement on 2024-07-01 10:00
    restate_dt = datetime(2024, 7, 1, 10, 0)
    orig_q3.valid_to = restate_dt  # Original expires when restatement is effective

    restated_q3 = FinancialStatement(
        isin="INE011A01011",
        period_start=date(2023, 10, 1),
        period_end=date(2023, 12, 31),
        period_type="QUARTERLY",
        consolidated=True,
        currency="INR",
        unit_multiplier=1.0,
        published_at=restate_dt,
        ingested_at=restate_dt,
        valid_from=restate_dt,
        valid_to=None,
        is_restatement=True,
        supersedes_id=orig_q3.id,
        source_url="https://nseindia.com/restated",
        source_type="NSE_XBRL"
    )
    db_session.add(restated_q3)
    db_session.flush()

    db_session.add_all([
        FinancialLineItem(statement_id=restated_q3.id, item_code="REV", value=120.0),
        FinancialLineItem(statement_id=restated_q3.id, item_code="EBITDA", value=25.0),
        FinancialLineItem(statement_id=restated_q3.id, item_code="PAT", value=10.0),  # Adjusted down
    ])
    db_session.commit()

    ttm_agg = TTMAggregator(db_session)

    # 1. Backtest query on 2024-06-01: must see original PAT = 60.0
    ttm_before = ttm_agg.get_ttm_metrics("INE011A01011", cutoff_timestamp=datetime(2024, 6, 1, 12, 0))
    assert ttm_before["PAT"] == 60.0

    # 2. Query on 2024-07-15: must see restated PAT = 54.0
    ttm_after = ttm_agg.get_ttm_metrics("INE011A01011", cutoff_timestamp=datetime(2024, 7, 15, 12, 0))
    assert ttm_after["PAT"] == 54.0
