"""Refresh the latest verified NSE EOD snapshot and optional static exports."""
import argparse
from datetime import date
import json
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db.connection import get_session_factory
from src.db.models import PriceRaw, Security
from src.ingestion.daily_refresh import export_static_snapshot, refresh_nse_snapshot


def parse_args():
    parser = argparse.ArgumentParser(
        description="Validate and persist TejHQ's latest complete NSE EOD snapshot."
    )
    parser.add_argument(
        "--export-static",
        action="store_true",
        help="Write data/latest_quotes.json and data/market_data_status.json.",
    )
    parser.add_argument("--minimum-coverage", type=int, default=1_000)
    parser.add_argument("--maximum-status-age-days", type=int, default=7)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    session = get_session_factory()()
    try:
        result = refresh_nse_snapshot(
            session,
            minimum_coverage=args.minimum_coverage,
            maximum_status_age_days=args.maximum_status_age_days,
        )
        if args.export_static:
            trade_date = date.fromisoformat(result.trading_date)
            rows = session.query(PriceRaw).filter(
                PriceRaw.trade_date == trade_date
            ).all()
            securities = {
                security.isin: security
                for security in session.query(Security).filter(
                    Security.isin.in_([row.isin for row in rows])
                )
            }
            export_static_snapshot(result, rows, securities, Path("data"))
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"Market data refresh failed: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
