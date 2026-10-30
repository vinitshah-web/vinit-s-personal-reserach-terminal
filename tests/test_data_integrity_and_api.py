"""Acceptance Tests: Database rollback, duplicate ingestion handling, and FastAPI 3-part envelope."""
import pytest
from datetime import date, datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from src.db.models import Security, PriceRaw
from src.api.main import app, get_db


def test_duplicate_ingestion_and_rollback(db_session):
    """
    Acceptance Test 11: Idempotent ingestion and database rollback.
    Inserting duplicate primary key (isin, trade_date) into PriceRaw raises IntegrityError
    and transaction rollback leaves previous database state pristine.
    """
    p1 = PriceRaw(
        isin="INE002A01018",
        trade_date=date(2024, 1, 5),
        close_raw=2840.0,
        volume_raw=1000000,
        source_file="bhav1.csv",
        file_hash="hash1",
        ingested_at=datetime.now(timezone.utc)
    )
    db_session.add(p1)
    db_session.commit()

    # Attempt duplicate insert
    p2 = PriceRaw(
        isin="INE002A01018",
        trade_date=date(2024, 1, 5),  # Same PK!
        close_raw=2850.0,
        volume_raw=1200000,
        source_file="bhav2.csv",
        file_hash="hash2",
        ingested_at=datetime.now(timezone.utc)
    )
    db_session.add(p2)
    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()

    # Assert database recovered and p1 is intact
    rows = db_session.query(PriceRaw).filter(PriceRaw.isin == "INE002A01018").all()
    assert len(rows) == 1
    assert rows[0].close_raw == 2840.0


def test_api_three_part_envelope_and_metadata(db_session):
    """
    Acceptance Test 12: FastAPI REST service returns 3-part envelope (facts | metrics | forecasts)
    with explicit formula references and synthetic data watermark.
    """
    # Seed a price row
    p = PriceRaw(
        isin="INE002A01018",
        trade_date=date(2024, 1, 5),
        close_raw=2840.0,
        volume_raw=1500000,
        source_file="sample_bhavcopy.csv",
        file_hash="sha256_mock_hash",
        ingested_at=datetime.now(timezone.utc)
    )
    db_session.add(p)
    db_session.commit()

    # Override FastAPI get_db dependency
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    try:
        # Health check
        h = client.get("/health")
        assert h.status_code == 200
        assert h.json()["status"] == "ok"

        # Query summary for Reliance
        resp = client.get("/api/v1/stock/INE002A01018/summary?as_of_date=2024-01-05&mode=AS_KNOWN")
        assert resp.status_code == 200
        data = resp.json()

        # 1. Structure validation
        assert "facts" in data
        assert "metrics" in data
        assert "forecasts" in data
        assert "metadata" in data

        # 2. Metadata & data policy
        assert data["metadata"]["data_policy"] == "NO_SYNTHETIC_MARKET_DATA"
        assert data["metadata"]["query_mode"] == "AS_KNOWN"

        # 3. Facts
        assert data["facts"]["security_profile"]["company_name"] == "Reliance Industries Limited"
        assert data["facts"]["security_profile"]["is_financial"] is False
        assert data["facts"]["market_observation"]["close_raw"] == 2840.0
        assert data["facts"]["market_observation"]["file_hash"] == "sha256_mock_hash"

        # 4. Metrics fail closed when the fixture has no reported statement.
        assert "dupont_5factor" in data["metrics"]
        assert data["metrics"]["dupont_5factor"]["status"] == "NOT_CALCULATED"

        # 5. Forecasts require explicit assumptions rather than hard-coded values.
        assert "dcf_valuation" in data["forecasts"]
        assert data["forecasts"]["dcf_valuation"]["status"] == "NOT_CALCULATED"
    finally:
        app.dependency_overrides.clear()
