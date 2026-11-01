"""Enrich missing company profiles and statements using the existing keyless adapter.

Run intentionally when network access is available. Refreshes a bounded batch,
keeps existing caches on provider failure, and never invents missing statements.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.ingestion.providers import FinancialsAdapter


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=25)
    parser.add_argument('--symbols', nargs='*', default=[])
    parser.add_argument('--refresh-all', action='store_true', help='Recheck all selected issuers, including existing profiles.')
    parser.add_argument('--maximum-seconds', type=int, default=10800)
    parser.add_argument('--status-output', default=None)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error('--limit must be positive')
    rows = json.loads(Path('data/securities_search_index.json').read_text())
    candidates = []
    for row in rows:
        if row.get('exchange', 'NSE') != 'NSE':
            continue
        ticker = row['ticker']
        if args.symbols and ticker not in args.symbols:
            continue
        path = Path('data/dossier_cache') / f'{ticker}.json'
        if not args.refresh_all and not args.symbols and path.exists():
            cached = json.loads(path.read_text())
            if cached.get('financial_statements') and cached.get('business_summary'):
                continue
        candidates.append(ticker)
    started = time.monotonic()
    result = {'attempted_at': datetime.now(timezone.utc).isoformat(), 'selected': min(len(candidates), args.limit), 'requested': 0, 'enriched': [], 'unavailable': [], 'incomplete': False}
    for ticker in candidates[:args.limit]:
        if time.monotonic() - started > args.maximum_seconds:
            result['incomplete'] = True
            break
        result['requested'] += 1
        row = FinancialsAdapter.get_company_dossier(ticker, allow_live=True)
        if row.get('financial_statements') or row.get('business_summary'):
            result['enriched'].append(ticker)
        else:
            result['unavailable'].append(ticker)
        time.sleep(0.5)
    result['status'] = 'INCOMPLETE' if result['incomplete'] else ('COMPLETED_WITH_GAPS' if result['unavailable'] else 'COMPLETED')
    if args.status_output:
        path = Path(args.status_output)
        temporary = path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(result, indent=2))
        temporary.replace(path)
    print(json.dumps(result, indent=2))
    return 1 if result['incomplete'] or (result['requested'] and not result['enriched']) else 0


if __name__ == '__main__':
    raise SystemExit(main())
