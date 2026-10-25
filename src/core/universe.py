"""Point-in-time universe selection to eliminate survivorship and lookahead bias.
Supports two distinct operational modes:
- AS_KNOWN: Strict operational platform knowledge (ingested_at <= cutoff)
- RECONSTRUCTED: Proven market availability (published_at <= cutoff)
"""
from datetime import date, datetime, timezone
from enum import Enum
from typing import List, Optional
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from src.db.models import Security, IndexConstituent, FinancialStatement, FinancialLineItem


class PITMode(str, Enum):
    AS_KNOWN = "AS_KNOWN"
    RECONSTRUCTED = "RECONSTRUCTED"


class PointInTimeUniverse:
    def __init__(self, session: Session):
        self.session = session

    def get_tradable_universe(
        self,
        as_of_date: date,
        allowed_series: List[str] = None
    ) -> List[Security]:
        """
        Returns all securities actively listed on the specified historical date.
        Delisted stocks appear if listing_date <= as_of_date < delisting_date.
        Newly listed stocks after as_of_date are strictly excluded.
        """
        if allowed_series is None:
            allowed_series = ["EQ", "BE"]

        query = self.session.query(Security).filter(
            Security.listing_date <= as_of_date,
            Security.series.in_(allowed_series)
        )
        query = query.filter(
            or_(Security.delisting_date.is_(None), Security.delisting_date > as_of_date)
        )
        return query.all()

    def get_point_in_time_financials(
        self,
        isin: str,
        cutoff_timestamp: datetime,
        as_of_period_end: Optional[date] = None,
        mode: PITMode = PITMode.AS_KNOWN
    ) -> Optional[FinancialStatement]:
        """
        Point-in-Time financial statement retriever supporting both AS_KNOWN and RECONSTRUCTED modes.
        - AS_KNOWN: Record must have been ingested_at <= cutoff_timestamp.
        - RECONSTRUCTED: Record must have been published_at <= cutoff_timestamp.
        Guarantees that after-market disclosures do not leak into queries prior to publication/ingestion.
        Preserves restatement versions: returns the version valid at the cutoff timestamp.
        """
        # Normalize timezone to UTC naive for consistent SQLite storage comparison
        if cutoff_timestamp.tzinfo is not None:
            cutoff_timestamp = cutoff_timestamp.astimezone(timezone.utc).replace(tzinfo=None)

        query = self.session.query(FinancialStatement).filter(
            FinancialStatement.isin == isin,
            FinancialStatement.consolidated == True
        )

        if as_of_period_end:
            query = query.filter(FinancialStatement.period_end <= as_of_period_end)

        if mode == PITMode.AS_KNOWN:
            query = query.filter(
                FinancialStatement.ingested_at <= cutoff_timestamp,
                FinancialStatement.valid_from <= cutoff_timestamp,
                or_(
                    FinancialStatement.valid_to.is_(None),
                    FinancialStatement.valid_to > cutoff_timestamp
                )
            )
        elif mode == PITMode.RECONSTRUCTED:
            query = query.filter(
                FinancialStatement.published_at <= cutoff_timestamp,
                or_(
                    FinancialStatement.restated_at.is_(None),
                    FinancialStatement.restated_at > cutoff_timestamp
                )
            )

        return query.order_by(FinancialStatement.period_end.desc(), FinancialStatement.published_at.desc()).first()
