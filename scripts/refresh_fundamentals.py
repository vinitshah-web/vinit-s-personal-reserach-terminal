"""Build an atomic, auditable fundamentals snapshot for listed instruments."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, Iterable, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from yfinance.data import YfData

from src.ingestion.fundamentals_snapshot import normalize_yahoo_quote, yahoo_symbol


YAHOO_QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"


def chunks(items: List[Dict[str, Any]], size: int) -> Iterable[List[Dict[str, Any]]]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


def fetch_batch(data_client: YfData, instruments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    provider_symbols = [
        yahoo_symbol(row["ticker"], row.get("exchange", "NSE"))
        for row in instruments
    ]
    response = data_client.get(
        YAHOO_QUOTE_URL,
        params={"symbols": ",".join(provider_symbols)},
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Yahoo quote endpoint returned HTTP {response.status_code}.")
    payload = response.json()
    results = payload.get("quoteResponse", {}).get("result")
    if not isinstance(results, list):
        raise RuntimeError("Yahoo quote endpoint returned no result array.")
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default="data/securities_search_index.json")
    parser.add_argument("--output", default="data/fundamentals_snapshot.json")
    parser.add_argument("--exchange", choices=("NSE", "BSE", "ALL"), default="ALL")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--pause-seconds", type=float, default=0.25)
    parser.add_argument("--maximum-failure-rate", type=float, default=0.10)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    index_path = Path(args.index)
    output_path = Path(args.output)
    instruments = json.loads(index_path.read_text(encoding="utf-8"))
    instruments = [
        row for row in instruments
        if args.exchange == "ALL" or str(row.get("exchange", "NSE")).upper() == args.exchange
    ]
    if args.limit > 0:
        instruments = instruments[:args.limit]
    if not instruments:
        print("No instruments selected for fundamentals refresh.", file=sys.stderr)
        return 1

    existing_payload: Dict[str, Any] = {}
    if output_path.exists():
        try:
            existing_payload = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing_payload = {}
    existing_rows = existing_payload.get("data", {})
    if not isinstance(existing_rows, dict):
        existing_rows = {}

    data_client = YfData()
    retrieved_at = datetime.now(timezone.utc)
    normalized: Dict[str, Dict[str, Any]] = {}
    failed_batches: List[Dict[str, Any]] = []
    requested = 0

    for batch_number, batch in enumerate(chunks(instruments, args.batch_size), start=1):
        requested += len(batch)
        try:
            provider_rows = fetch_batch(data_client, batch)
            by_symbol = {str(row.get("symbol", "")).upper(): row for row in provider_rows}
            for instrument in batch:
                provider_symbol = yahoo_symbol(
                    instrument["ticker"], instrument.get("exchange", "NSE")
                )
                provider_row = by_symbol.get(provider_symbol.upper())
                if provider_row is None:
                    continue
                row = normalize_yahoo_quote(provider_row, instrument, retrieved_at)
                if row["data_status"] == "AVAILABLE":
                    normalized[row["key"]] = row
        except Exception as exc:
            failed_batches.append({
                "batch": batch_number,
                "count": len(batch),
                "error": str(exc),
            })
        if args.pause_seconds > 0:
            time.sleep(args.pause_seconds)

    failure_rate = (requested - len(normalized)) / requested
    if failure_rate > args.maximum_failure_rate:
        print(
            f"Fundamentals coverage rejected: {len(normalized)}/{requested} rows; "
            f"failure rate {failure_rate:.2%} exceeds {args.maximum_failure_rate:.2%}.",
            file=sys.stderr,
        )
        if failed_batches:
            print(json.dumps(failed_batches, indent=2), file=sys.stderr)
        return 1

    merged = dict(existing_rows)
    merged.update(normalized)
    payload = {
        "status": "VERIFIED_SECONDARY_SOURCE",
        "source": "Yahoo Finance quote feed",
        "source_class": "SECONDARY_AGGREGATOR",
        "retrieved_at": retrieved_at.isoformat(),
        "requested_count": requested,
        "refreshed_count": len(normalized),
        "total_cached_count": len(merged),
        "failed_batches": failed_batches,
        "data": merged,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    temporary.replace(output_path)
    print(json.dumps({key: value for key, value in payload.items() if key != "data"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
