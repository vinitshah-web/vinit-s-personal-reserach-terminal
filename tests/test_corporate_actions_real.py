"""Tests for real NSE corporate actions parser on authentic bc23102026.csv."""
import zipfile
import io
from pathlib import Path
from datetime import date
import pytest
from src.ingestion.corporate_actions import CorporateActionParser


def test_parse_real_nse_bc_csv():
    zip_path = Path("Reports-Daily-Multiple.zip")
    if not zip_path.exists():
        pytest.skip("Reports-Daily-Multiple.zip not found in workspace")

    with zipfile.ZipFile(zip_path) as outer_z:
        assert "PR231026.zip" in outer_z.namelist()
        pr_bytes = outer_z.read("PR231026.zip")
        with zipfile.ZipFile(io.BytesIO(pr_bytes)) as pr_z:
            assert "bc23102026.csv" in pr_z.namelist()
            bc_text = pr_z.read("bc23102026.csv").decode("utf-8", errors="ignore")

    symbol_map = {
        "TECHM": "INE669C01036",
        "AZADIND": "INE566M01017",
        "LTM": "INE214T01019",
        "ICICIGI": "INE765G01017",
        "OBEROIRLTY": "INE093I01010",
        "CHENNPETRO": "INE178A01016"
    }

    parser = CorporateActionParser()
    recs = parser.parse_nse_bc_csv(bc_text, symbol_map)
    assert len(recs) >= 6

    # 1. TECHM Dividend of Rs 15 on 2026-10-23
    techm_ca = [r for r in recs if r["isin"] == "INE669C01036"][0]
    assert techm_ca["action_type"] == "dividend"
    assert techm_ca["dividend_per_share"] == 15.0
    assert techm_ca["ex_date"] == date(2026, 10, 23)

    # 2. AZADIND Split from Rs 10 to Rs 2 (Factor = 0.20)
    azad_ca = [r for r in recs if r["isin"] == "INE566M01017"][0]
    assert azad_ca["action_type"] == "split"
    assert azad_ca["ratio_numerator"] == 5
    assert azad_ca["ratio_denominator"] == 1
    assert azad_ca["adj_factor"] == 0.20
    assert azad_ca["ex_date"] == date(2026, 10, 23)

    # 3. LTM Dividend of Rs 25
    ltm_ca = [r for r in recs if r["isin"] == "INE214T01019"][0]
    assert ltm_ca["dividend_per_share"] == 25.0

    # 4. CHENNPETRO Future Ex-date 2026-10-30
    chenn_ca = [r for r in recs if r["isin"] == "INE178A01016"][0]
    assert chenn_ca["ex_date"] == date(2026, 10, 30)
    assert chenn_ca["effective_from"] == date(2026, 10, 30)
