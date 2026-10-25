"""Trailing Twelve Month (TTM) Aggregator with strict Point-In-Time gating.
Aggregates quarterly flow line items (Revenue, EBITDA, PAT, CFO) over 4 consecutive quarters.
Guarantees zero future data leakage and handles restatement versioning.
"""
from datetime import date, datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session
from src.db.models import FinancialStatement, FinancialLineItem


class IncompleteTTMDataError(ValueError):
    """Raised when fewer than 4 consecutive quarters exist or there are missing periods."""
    pass


class TTMAggregator:
    def __init__(self, session: Session):
        self.session = session

    def get_ttm_metrics(
        self,
        isin: str,
        cutoff_timestamp: datetime,
        as_of_period_end: Optional[date] = None,
        consolidated: bool = True
    ) -> Dict[str, float]:
        """
        Computes 4-quarter TTM sum for flow metrics as of cutoff_timestamp.
        Requires exactly 4 consecutive quarterly statements available before cutoff_timestamp.
        """
        if cutoff_timestamp.tzinfo is not None:
            cutoff_timestamp = cutoff_timestamp.astimezone(timezone.utc).replace(tzinfo=None)

        # Query all quarterly statements known before cutoff_timestamp
        query = self.session.query(FinancialStatement).filter(
            FinancialStatement.isin == isin,
            FinancialStatement.period_type == "QUARTERLY",
            FinancialStatement.consolidated == consolidated,
            FinancialStatement.published_at <= cutoff_timestamp,
            FinancialStatement.ingested_at <= cutoff_timestamp,
            FinancialStatement.valid_from <= cutoff_timestamp,
            or_(
                FinancialStatement.valid_to.is_(None),
                FinancialStatement.valid_to > cutoff_timestamp
            )
        )

        if as_of_period_end:
            query = query.filter(FinancialStatement.period_end <= as_of_period_end)

        # Order by period_end descending
        statements = query.order_by(FinancialStatement.period_end.desc()).all()

        # Deduplicate if any duplicate period_end exists (pick most recent published_at)
        unique_periods = {}
        for stmt in statements:
            if stmt.period_end not in unique_periods:
                unique_periods[stmt.period_end] = stmt

        sorted_stmts = sorted(unique_periods.values(), key=lambda s: s.period_end, reverse=True)

        if len(sorted_stmts) < 4:
            raise IncompleteTTMDataError(
                f"Cannot compute TTM for {isin}: only {len(sorted_stmts)} valid quarters available prior to {cutoff_timestamp} (minimum 4 required)."
            )

        # Take latest 4 consecutive quarters
        ttm_stmts = sorted_stmts[:4]

        # Verify continuity: difference between adjacent period_ends should be ~90 days (60 to 125 days)
        for i in range(len(ttm_stmts) - 1):
            gap_days = (ttm_stmts[i].period_end - ttm_stmts[i + 1].period_end).days
            if gap_days < 60 or gap_days > 125:
                raise IncompleteTTMDataError(
                    f"Gap detected between quarters {ttm_stmts[i].period_end} and {ttm_stmts[i + 1].period_end} ({gap_days} days). TTM requires 4 consecutive quarters."
                )

        # Sum flow line items
        flow_codes = ["REV", "EBITDA", "EBIT", "PAT", "CFO", "INT_EXP", "DEP_AMORT"]
        ttm_sums = {code: 0.0 for code in flow_codes}
        item_found_counts = {code: 0 for code in flow_codes}

        for stmt in ttm_stmts:
            items = {item.item_code: item.value for item in stmt.line_items}
            for code in flow_codes:
                if code in items and items[code] is not None:
                    # Apply unit multiplier (e.g. Crores to absolute or consistent)
                    val = items[code] * stmt.unit_multiplier
                    ttm_sums[code] += val
                    item_found_counts[code] += 1

        # Only retain metrics that appeared in all 4 quarters
        result = {}
        for code, count in item_found_counts.items():
            if count == 4:
                result[code] = ttm_sums[code]

        # Latest balance sheet snapshot items (from the most recent quarter)
        latest_stmt = ttm_stmts[0]
        latest_items = {item.item_code: item.value for item in latest_stmt.line_items}
        stock_codes = ["TOTAL_DEBT", "CASH_EQUIV", "TOTAL_EQUITY", "TOTAL_ASSETS"]
        for sc in stock_codes:
            if sc in latest_items and latest_items[sc] is not None:
                result[sc] = latest_items[sc] * latest_stmt.unit_multiplier

        result["latest_period_end"] = latest_stmt.period_end.isoformat()
        result["quarters_count"] = 4
        return result
