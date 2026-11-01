"""Validate committed data and report actual field-level coverage without network I/O."""
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def audit(root=ROOT):
    data = root / 'data'
    index = json.loads((data / 'securities_search_index.json').read_text())
    quotes = json.loads((data / 'latest_quotes.json').read_text())
    status = json.loads((data / 'market_data_status.json').read_text())
    facts = json.loads((data / 'fundamentals_snapshot.json').read_text())['data']
    errors, exchanges, seen = [], {}, set()
    for row in index:
        exchange = row.get('exchange') or 'NSE'
        key = f"{exchange}:{row['ticker']}"
        if key in seen:
            errors.append(f'Duplicate security key: {key}')
        seen.add(key)
        counts = exchanges.setdefault(exchange, Counter())
        counts['listed'] += 1
        quote = quotes.get(row['ticker'] if exchange == 'NSE' else key)
        record = status.get('exchanges', {}).get(exchange, status if exchange == 'NSE' else {})
        if quote:
            if quote.get('source_hash') != record.get('source_hash'):
                errors.append(f'Quote snapshot hash mismatch: {key}')
            volume = quote.get('volume')
            if not isinstance(volume, (float,int)) or not math.isfinite(volume) or volume < 0 or int(volume) != volume:
                errors.append(f'Invalid volume: {key}')
            if quote.get('isin') != row.get('isin'):
                errors.append(f'Quote identity mismatch: {key}')
            vals = [quote.get(field) for field in ('open', 'high', 'low', 'close')]
            if not all(isinstance(v,(float,int)) and math.isfinite(v) and v > 0 for v in vals):
                errors.append(f'Invalid OHLC: {key}')
            elif not (vals[2] <= vals[0] <= vals[1] and vals[2] <= vals[3] <= vals[1]):
                errors.append(f'Impossible OHLC: {key}')
            if record.get('status') == 'VERIFIED' and quote.get('trade_date') == record.get('trading_date'):
                counts['verified_quotes'] += 1
        fact = facts.get(key, {})
        if fact:
            counts['fundamentals_rows'] += 1
            if fact.get('isin') != row.get('isin'):
                errors.append(f'Fundamentals identity mismatch: {key}')
        for field in ('pe_ratio','shares_outstanding_cr','fifty_two_week_high','fifty_two_week_low','pb_ratio'):
            if fact.get(field) is not None:
                counts[field] += 1
    caches = list((data / 'dossier_cache').glob('*.json'))
    detailed = [json.loads(p.read_text()) for p in caches]
    return {'status': 'PASSED' if not errors else 'FAILED', 'errors': errors,
            'exchanges': {key:dict(value) for key,value in exchanges.items()},
            'detailed_profiles': sum(bool(r.get('business_summary')) and not r['business_summary'].endswith(' is an Indian publicly traded enterprise.') for r in detailed),
            'statement_caches': sum(bool(r.get('financial_statements')) for r in detailed),
            'limits': ['Coverage describes committed data, not a live provider verification.',
                       'P/B needs dated balance-sheet equity and a compatible price date.',
                       'CFO less capex is not unlevered FCFF; scenario inputs remain explicit.']}


if __name__ == '__main__':
    result = audit()
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(bool(result['errors']))
