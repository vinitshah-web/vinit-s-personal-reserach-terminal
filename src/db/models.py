"""SQLAlchemy 2.0 Declarative Models for NSE Equity Intelligence Platform.
Dialect-agnostic design fully portable between SQLite and PostgreSQL.
"""
from datetime import date, datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    String, Boolean, Date, DateTime, Integer, BigInteger,
    Float, Text, ForeignKey, UniqueConstraint, Index, CheckConstraint
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utc_now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Security(Base):
    __tablename__ = "security"

    isin: Mapped[str] = mapped_column(String(12), primary_key=True)
    ticker_current: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    sector: Mapped[Optional[str]] = mapped_column(String(100))
    industry: Mapped[Optional[str]] = mapped_column(String(100))
    listing_date: Mapped[date] = mapped_column(Date, nullable=False)
    delisting_date: Mapped[Optional[date]] = mapped_column(Date)
    series: Mapped[str] = mapped_column(String(5), nullable=False, default="EQ")
    is_financial: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)

    # Relationships
    prices: Mapped[List["PriceRaw"]] = relationship(back_populates="security", cascade="all, delete-orphan")
    corporate_actions: Mapped[List["CorporateAction"]] = relationship(back_populates="security", cascade="all, delete-orphan")
    statements: Mapped[List["FinancialStatement"]] = relationship(back_populates="security", cascade="all, delete-orphan")


class ISINHistory(Base):
    __tablename__ = "isin_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    old_isin: Mapped[str] = mapped_column(String(12), nullable=False)
    new_isin: Mapped[str] = mapped_column(String(12), ForeignKey("security.isin"), nullable=False)
    change_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)


class PriceRaw(Base):
    __tablename__ = "price_raw"

    isin: Mapped[str] = mapped_column(String(12), ForeignKey("security.isin"), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    open_raw: Mapped[Optional[float]] = mapped_column(Float)
    high_raw: Mapped[Optional[float]] = mapped_column(Float)
    low_raw: Mapped[Optional[float]] = mapped_column(Float)
    close_raw: Mapped[float] = mapped_column(Float, nullable=False)
    volume_raw: Mapped[int] = mapped_column(BigInteger, nullable=False)
    delivery_pct: Mapped[Optional[float]] = mapped_column(Float)
    source_file: Mapped[str] = mapped_column(String(100), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now)

    security: Mapped["Security"] = relationship(back_populates="prices")

    __table_args__ = (
        Index("idx_price_raw_isin_date", "isin", "trade_date"),
    )


class CorporateAction(Base):
    __tablename__ = "corporate_action"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    isin: Mapped[str] = mapped_column(String(12), ForeignKey("security.isin"), nullable=False)
    ex_date: Mapped[date] = mapped_column(Date, nullable=False)
    record_date: Mapped[Optional[date]] = mapped_column(Date)
    action_type: Mapped[str] = mapped_column(String(30), nullable=False)
    ratio_numerator: Mapped[Optional[int]] = mapped_column(Integer)
    ratio_denominator: Mapped[Optional[int]] = mapped_column(Integer)
    dividend_per_share: Mapped[Optional[float]] = mapped_column(Float)
    dividend_type: Mapped[Optional[str]] = mapped_column(String(20))
    subscription_price: Mapped[Optional[float]] = mapped_column(Float)
    details_json: Mapped[Optional[str]] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date)
    adj_factor: Mapped[Optional[float]] = mapped_column(Float)

    security: Mapped["Security"] = relationship(back_populates="corporate_actions")

    __table_args__ = (
        UniqueConstraint("isin", "ex_date", "action_type", name="uq_ca_isin_ex_type"),
        Index("idx_ca_isin_ex", "isin", "ex_date"),
    )


class FinancialStatement(Base):
    __tablename__ = "financial_statement"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    isin: Mapped[str] = mapped_column(String(12), ForeignKey("security.isin"), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    period_type: Mapped[str] = mapped_column(String(15), nullable=False)
    consolidated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    unit_multiplier: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utc_now)
    restated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    is_restatement: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supersedes_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("financial_statement.id"))

    valid_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)

    security: Mapped["Security"] = relationship(back_populates="statements")
    line_items: Mapped[List["FinancialLineItem"]] = relationship(back_populates="statement", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_fs_isin_period", "isin", "period_end"),
        Index("idx_fs_validity", "valid_from", "valid_to"),
    )


class LineItemDef(Base):
    __tablename__ = "line_item_def"

    item_code: Mapped[str] = mapped_column(String(50), primary_key=True)
    item_name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    applicable_to: Mapped[str] = mapped_column(String(50), nullable=False)
    unit_type: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)


class FinancialLineItem(Base):
    __tablename__ = "financial_line_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    statement_id: Mapped[int] = mapped_column(Integer, ForeignKey("financial_statement.id"), nullable=False)
    item_code: Mapped[str] = mapped_column(String(50), ForeignKey("line_item_def.item_code"), nullable=False)
    value: Mapped[Optional[float]] = mapped_column(Float)
    is_estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    statement: Mapped["FinancialStatement"] = relationship(back_populates="line_items")

    __table_args__ = (
        UniqueConstraint("statement_id", "item_code", name="uq_fs_item"),
    )


class IndexConstituent(Base):
    __tablename__ = "index_constituent"

    index_name: Mapped[str] = mapped_column(String(50), primary_key=True)
    isin: Mapped[str] = mapped_column(String(12), ForeignKey("security.isin"), primary_key=True)
    inclusion_date: Mapped[date] = mapped_column(Date, primary_key=True)
    exclusion_date: Mapped[Optional[date]] = mapped_column(Date)
    weight: Mapped[Optional[float]] = mapped_column(Float)
    source_url: Mapped[Optional[str]] = mapped_column(Text)


class IndexPrice(Base):
    __tablename__ = "index_price"

    index_name: Mapped[str] = mapped_column(String(50), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[Optional[float]] = mapped_column(Float)
    high: Mapped[Optional[float]] = mapped_column(Float)
    low: Mapped[Optional[float]] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[Optional[int]] = mapped_column(BigInteger)
    turnover_cr: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)


class GovernanceEvent(Base):
    __tablename__ = "governance_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    isin: Mapped[str] = mapped_column(String(12), ForeignKey("security.isin"), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # AUDITOR_RESIGNATION, PROMOTER_PLEDGE, BULK_DEAL, EARNINGS
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), default="INFO")  # INFO, MEDIUM, HIGH, CRITICAL
    metric_value: Mapped[Optional[float]] = mapped_column(Float)  # e.g. pledge % or deal value
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)

    __table_args__ = (
        Index("idx_gov_event_isin_date", "isin", "event_date"),
    )


