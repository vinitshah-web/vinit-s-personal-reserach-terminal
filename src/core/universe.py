"""Point-in-time universe selection to eliminate survivorship and lookahead bias."""
from datetime import date, datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from src.db.models import Security, IndexConstituent, FinancialStatement, FinancialLineItem


class PointInTimeUniverse:
    def __init__(self, session: Session):
        self.session = session

    def get_tradable_universe(
        self,
        as_of_date: date,
        allowed_series: List[str] = None
    ) -> List[Security]:
        """
        Returns all securities that were actively listed on the specified historical date.
        Delisted stocks appear if listing_date <= as_of_date < delisting_date.
        Newly listed stocks after as_of_date are strictly excluded.
        """
        if allowed_series is None:
            allowed_series = ["EQ", "BE"]

        query = self.session.query(Security).filter(
            Security.listing_date <= as_of_date,
            Security.series.isin(allowed_series)
        )
        # Check delisting
        query = query.filter(
            (Security.delisting_date.is_(None)) | (Security.delisting_date > as_of_date)
        )
        return query.all()

    def get_point_in_time_financials(
        self,
        isin: str,
        as_of_timestamp: datetime,
        as_of_date: date
    ) -> Optional[FinancialStatement]:
        """
        Point-in-Time financial statement retriever.
        Guarantees no lookahead bias:
        1. Statement period_end <= as_of_date
        2. Platform ingested_at <= as_of_timestamp
        3. valid_from <= as_of_timestamp AND (valid_to IS NULL OR valid_to > as_of_timestamp)
        """
        stmt = self.session.query(FinancialStatement).filter(
            FinancialStatement.isin == isin,
            FinancialStatement.period_end <= as_of_date,
            FinancialStatement.ingested_at <= as_of_timestamp,
            FinancialStatement.valid_from <= as_of_timestamp,
            (FinancialStatement.valid_to.is_(None) | (FinancialStatement.valid_to > as_of_timestamp)),
            FinancialStatement.consolidated == True
        ).order_by(FinancialStatement.period_end.desc()).first()
        return stmt
