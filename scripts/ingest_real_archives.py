"""Ingestion script for official NSE Daily Archives from workspace root.
Unpacks Reports-Daily-Multiple.zip:
1. Unified Bhavcopy (2026-10-22) -> price_raw
2. Legacy PR Bhavcopy pd23102026.csv (2026-10-23) -> price_raw
3. Official announcements an23102026.txt -> governance_event
4. Index levels NIFTY 50-25-10-2025-to-25-10-2026.csv -> index_price
"""
import sys
import os
import zipfile
import io
from pathlib import Path
from datetime import date, datetime, timezone
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.connection import get_session_factory, get_engine
from src.db.models import Base, Security, PriceRaw, GovernanceEvent, IndexPrice, CorporateAction
from src.ingestion.bhavcopy import BhavcopyIngester
from src.ingestion.announcements import AnnouncementParser
from src.ingestion.corporate_actions import CorporateActionParser
from src.ingestion.index_parser import IndexDataIngester
from src.db.seed_defs import seed_standard_line_items


def ingest_workspace_archives():
    print("=== Ingesting Official NSE Archives into Platform Database ===")
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    session_factory = get_session_factory()
    session = session_factory()

    try:
        # Seed definitions
        seed_standard_line_items(session)

        # 1. Ingest Index Prices (Nifty 50)
        idx_csv = Path("NIFTY 50-25-10-2025-to-25-10-2026.csv")
        if idx_csv.exists():
            idx_ingester = IndexDataIngester(session)
            count = idx_ingester.ingest_csv(str(idx_csv), "NIFTY 50")
            print(f"[OK] Ingested {count} NIFTY 50 index daily prices.")

        # 2. Open Reports-Daily-Multiple.zip
        zip_path = Path("Reports-Daily-Multiple.zip")
        if not zip_path.exists():
            print("[WARN] Reports-Daily-Multiple.zip not found.")
            return

        with zipfile.ZipFile(zip_path) as outer_z:
            bhav_ingester = BhavcopyIngester()

            # A. Unified Bhavcopy (2026-10-22)
            if "BhavCopy_NSE_CM_0_0_0_20261022_F_0000.csv.zip" in outer_z.namelist():
                inner_zip_bytes = outer_z.read("BhavCopy_NSE_CM_0_0_0_20261022_F_0000.csv.zip")
                with zipfile.ZipFile(io.BytesIO(inner_zip_bytes)) as inner_z:
                    csv_name = inner_z.namelist()[0]
                    csv_bytes = inner_z.read(csv_name)
                    file_hash = bhav_ingester.compute_sha256(csv_bytes)
                    records = bhav_ingester.parse_bhavcopy_csv(
                        csv_bytes,
                        source_filename=csv_name,
                        file_hash=file_hash,
                        trade_date=date(2026, 10, 22)
                    )

                    # Ensure Securities exist for EQ/BE series
                    sec_count = 0
                    price_count = 0
                    for r in records:
                        srs = r["series"]
                        isin_code = r["isin"]
                        sym = r["ticker"]
                        if srs in ("EQ", "BE"):
                            sec = session.query(Security).filter(Security.isin == isin_code).first()
                            if not sec:
                                sec = Security(
                                    isin=isin_code,
                                    ticker_current=sym,
                                    company_name=sym,
                                    listing_date=date(2000, 1, 1),
                                    series=srs
                                )
                                session.add(sec)
                                sec_count += 1

                            existing_price = session.query(PriceRaw).filter(
                                PriceRaw.isin == isin_code,
                                PriceRaw.trade_date == r["trade_date"]
                            ).first()
                            if not existing_price:
                                pr = PriceRaw(
                                    isin=isin_code,
                                    trade_date=r["trade_date"],
                                    open_raw=r["open_raw"],
                                    high_raw=r["high_raw"],
                                    low_raw=r["low_raw"],
                                    close_raw=r["close_raw"],
                                    volume_raw=r["volume_raw"],
                                    delivery_pct=r["delivery_pct"],
                                    source_file=r["source_file"],
                                    file_hash=r["file_hash"]
                                )
                                session.add(pr)
                                price_count += 1

                    session.commit()
                    print(f"[OK] Ingested 2026-10-22 Unified Bhavcopy: {price_count} price rows ({sec_count} new securities).")

            # B. PR Archive (2026-10-23)
            if "PR231026.zip" in outer_z.namelist():
                pr_bytes = outer_z.read("PR231026.zip")
                with zipfile.ZipFile(io.BytesIO(pr_bytes)) as pr_z:
                    # Announcements
                    if "an23102026.txt" in pr_z.namelist():
                        an_text = pr_z.read("an23102026.txt").decode("utf-8", errors="ignore")
                        an_recs = AnnouncementParser.parse_announcements_text(an_text, date(2026, 10, 23))

                        gov_count = 0
                        for ar in an_recs:
                            sec = session.query(Security).filter(Security.ticker_current == ar["symbol"]).first()
                            if sec:
                                gov_ev = GovernanceEvent(
                                    isin=sec.isin,
                                    event_date=ar["trade_date"],
                                    event_type=ar["event_type"],
                                    title=f"{ar['symbol']} - {ar['category']}",
                                    description=ar["description"][:500],
                                    severity=ar["severity"],
                                    metric_value=ar.get("dividend_amount_per_share"),
                                    source_url="https://nseindia.com/reports/PR231026/an23102026.txt",
                                    published_at=datetime.now(timezone.utc)
                                )
                                session.add(gov_ev)
                                gov_count += 1
                        session.commit()
                        print(f"[OK] Ingested {gov_count} real corporate events from an23102026.txt into governance_event.")

                    # Real Corporate Actions from bc23102026.csv
                    if "bc23102026.csv" in pr_z.namelist():
                        bc_text = pr_z.read("bc23102026.csv").decode("utf-8", errors="ignore")
                        sym_map = {s.ticker_current: s.isin for s in session.query(Security).all()}
                        ca_parser = CorporateActionParser()
                        ca_recs = ca_parser.parse_nse_bc_csv(bc_text, sym_map)
                        ca_count = 0
                        for ca in ca_recs:
                            existing_ca = session.query(CorporateAction).filter(
                                CorporateAction.isin == ca["isin"],
                                CorporateAction.ex_date == ca["ex_date"],
                                CorporateAction.action_type == ca["action_type"]
                            ).first()
                            if not existing_ca:
                                row = CorporateAction(**ca)
                                session.add(row)
                                ca_count += 1
                        session.commit()
                        print(f"[OK] Ingested {ca_count} official corporate actions from bc23102026.csv.")

                    # Real Bhavcopy Prices for 2026-10-23 from pd23102026.csv
                    if "pd23102026.csv" in pr_z.namelist():
                        pd_bytes = pr_z.read("pd23102026.csv")
                        pd_hash = bhav_ingester.compute_sha256(pd_bytes)
                        sym_map = {s.ticker_current: s.isin for s in session.query(Security).all()}
                        records_23 = bhav_ingester.parse_bhavcopy_csv(
                            pd_bytes,
                            source_filename="pd23102026.csv",
                            file_hash=pd_hash,
                            trade_date=date(2026, 10, 23),
                            symbol_to_isin_map=sym_map
                        )
                        price23_count = 0
                        for r in records_23:
                            isin_code = r["isin"]
                            existing_price = session.query(PriceRaw).filter(
                                PriceRaw.isin == isin_code,
                                PriceRaw.trade_date == r["trade_date"]
                            ).first()
                            if not existing_price:
                                pr_row = PriceRaw(
                                    isin=isin_code,
                                    trade_date=r["trade_date"],
                                    open_raw=r["open_raw"],
                                    high_raw=r["high_raw"],
                                    low_raw=r["low_raw"],
                                    close_raw=r["close_raw"],
                                    volume_raw=r["volume_raw"],
                                    delivery_pct=r["delivery_pct"],
                                    source_file=r["source_file"],
                                    file_hash=r["file_hash"]
                                )
                                session.add(pr_row)
                                price23_count += 1
                        session.commit()
                        print(f"[OK] Ingested 2026-10-23 Bhavcopy prices: {price23_count} price rows from pd23102026.csv.")

        print("=== Workspace Archives Successfully Ingested ===")
    finally:
        session.close()


if __name__ == "__main__":
    ingest_workspace_archives()
