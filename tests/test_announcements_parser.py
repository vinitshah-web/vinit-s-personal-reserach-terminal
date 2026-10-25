"""Acceptance tests for NSE Corporate Action & LODR Announcements Parser."""
from datetime import date
import zipfile
import io
import pytest
from src.ingestion.announcements import AnnouncementParser


def test_announcement_parser_synthetic():
    sample_text = """
COMPANY NAME    SYMBOL    : ANNOUNCEMENTS
Chennai Petroleum Corporation Limited CHENNPETRO : Dividend CHENNPETRO : Chennai Petroleum Corporation Limited has informed the Exchange that Board of Directors at its meeting held on October 22, 2026, declared Interim Dividend of Rs. 25 per equity share.
Infosys Limited INFY : Auditor INFY : Infosys Limited has informed the Exchange regarding premature resignation of Statutory Auditor.
Tata Motors Limited TATAMOTORS : Shareholders meeting TATAMOTORS : Notice of Postal ballot.
"""
    records = AnnouncementParser.parse_announcements_text(sample_text, date(2026, 10, 23))
    assert len(records) == 3

    # Dividend announcement
    div_rec = [r for r in records if r["symbol"] == "CHENNPETRO"][0]
    assert div_rec["event_type"] == "DIVIDEND_DECLARATION"
    assert div_rec["dividend_amount_per_share"] == 25.0

    # Auditor resignation announcement
    aud_rec = [r for r in records if r["symbol"] == "INFY"][0]
    assert aud_rec["event_type"] == "AUDITOR_RESIGNATION"
    assert aud_rec["severity"] == "CRITICAL"


def test_announcement_parser_on_real_pr_zip():
    """Parses real announcements from Reports-Daily-Multiple.zip."""
    z = zipfile.ZipFile("Reports-Daily-Multiple.zip")
    pz = zipfile.ZipFile(io.BytesIO(z.read("PR231026.zip")))
    raw_text = pz.read("an23102026.txt").decode("utf-8", errors="ignore")

    records = AnnouncementParser.parse_announcements_text(raw_text, date(2026, 10, 23))
    assert len(records) > 100, f"Expected > 100 corporate announcements, got {len(records)}"

    # Check CHENNPETRO Rs 25 dividend announcement presence
    cp_recs = [r for r in records if r["symbol"] == "CHENNPETRO"]
    assert len(cp_recs) >= 1
    assert cp_recs[0]["dividend_amount_per_share"] == 25.0
