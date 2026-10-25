"""Pytest configuration and shared test fixtures."""
import pytest
from datetime import date, datetime
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from src.db.models import Base, Security, LineItemDef
from src.config_loader import ConfigLoader
from src.tax.engine import TaxEngine


@pytest.fixture
def config():
    loader = ConfigLoader()
    return loader.load_tax_rules()


@pytest.fixture
def model_params():
    loader = ConfigLoader()
    return loader.load_model_params()


@pytest.fixture
def tax_engine(config):
    return TaxEngine(config=config, allow_unverified=True)


@pytest.fixture
def db_session():
    """In-memory SQLite database session with PRAGMA foreign_keys = ON."""
    engine = create_engine("sqlite:///:memory:", echo=False)

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed essential securities
    sec1 = Security(
        isin="INE002A01018",
        ticker_current="RELIANCE",
        company_name="Reliance Industries Limited",
        sector="Energy",
        industry="Oil & Gas - Refining & Marketing",
        listing_date=date(1995, 1, 3),
        delisting_date=None,
        series="EQ",
        is_financial=False
    )
    sec2 = Security(
        isin="INE040A01034",
        ticker_current="HDFCBANK",
        company_name="HDFC Bank Limited",
        sector="Financial Services",
        industry="Private Sector Bank",
        listing_date=date(1996, 5, 19),
        delisting_date=None,
        series="EQ",
        is_financial=True
    )
    sec3 = Security(
        isin="INE123A01010",
        ticker_current="KFA",
        company_name="Kingfisher Airlines Limited",
        sector="Aviation",
        industry="Airlines",
        listing_date=date(2006, 6, 1),
        delisting_date=date(2014, 12, 1),  # Delisted historically
        series="EQ",
        is_financial=False
    )
    session.add_all([sec1, sec2, sec3])

    # Seed line item definitions
    items = [
        LineItemDef(item_code="REVENUE", item_name="Revenue from Operations", category="income_statement", applicable_to="all", unit_type="currency"),
        LineItemDef(item_code="EBITDA", item_name="EBITDA", category="income_statement", applicable_to="non_financial", unit_type="currency"),
        LineItemDef(item_code="EBIT", item_name="EBIT", category="income_statement", applicable_to="non_financial", unit_type="currency"),
        LineItemDef(item_code="EBT", item_name="Profit Before Tax", category="income_statement", applicable_to="all", unit_type="currency"),
        LineItemDef(item_code="PAT", item_name="Profit After Tax", category="income_statement", applicable_to="all", unit_type="currency"),
        LineItemDef(item_code="TOTAL_ASSETS", item_name="Total Assets", category="balance_sheet", applicable_to="all", unit_type="currency"),
        LineItemDef(item_code="EQUITY", item_name="Shareholders Equity", category="balance_sheet", applicable_to="all", unit_type="currency"),
    ]
    session.add_all(items)
    session.commit()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)
