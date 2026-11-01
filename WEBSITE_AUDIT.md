# Website audit and validation — 1 November 2026

## Pages reviewed

| Page | Findings and resulting behavior |
|---|---|
| Home / Overview | Removed hardcoded featured prices and unsupported macro claims; cards load dated snapshots and coverage. Search ranks the full index before limiting and rejects stale asynchronous results. |
| Research | Available cached facts survive null batch values. NSE/BSE issuer statements can share an exact ISIN. Network waits have timeouts. The calculator is linked and exchange selection survives ticker switching. |
| Compare | Fixed the API/UI response mismatch that hid available prices. Snapshot prices take precedence over older SQLite prices. Added input validation and shared quote checks. |
| Watchlist | Validates imported records, caps import size, deduplicates by exchange/symbol, escapes imported text, and checks quote status/date before display. |
| Reports | Replaced synthetic demo markdown with current snapshot reports, available sourced descriptions and cached statements. PDF detection now uses the health endpoint instead of unsupported HEAD routes. |
| Stock Intelligence | Redirects to working research while preserving the selected ticker/exchange. |
| Quant Lab | Replaced the synthetic prototype with a functioning company screener: exchange/search filters, price coverage filter, P/E and market-cap sorting, pagination and CSV export. |
| Valuation Lab | Explicitly labels inputs as assumptions, validates banking inputs and reverse-DCF solver bounds, and separates CFO less capex from unlevered FCFF. |
| Data Quality | Shows actual field coverage alongside dates and source hashes. |
| Shared UI / API | Local compiled CSS replaces runtime CDN dependency. Mobile navigation exposes all tools; inputs have accessible labels and keyboard focus styles. Snapshot requests are deduplicated per page. Added missing local page/asset routes and gzip responses. Interactive Yahoo scraping is replaced by explicit refresh commands. |

## Data evidence

`python scripts/audit_snapshots.py` validates security keys, quote/fundamental ISINs,
OHLC values, volume, snapshot hashes and field coverage across the committed files.
It found no errors:

| Exchange | Listed instruments | Verified dated prices | Fundamentals rows | Positive trailing P/E available |
|---|---:|---:|---:|---:|
| NSE | 3,392 | 2,926 | 2,945 | 2,441 |
| BSE | 2,678 | 2,678 | 2,677 | 2,288 |

There are 20 cached sourced business descriptions and 20 statement caches.
These are secondary-source extracts; this audit did not independently verify
company filings. A fundamentals row does not guarantee every field is available.
P/B remains blank where dated equity/price inputs are missing. Coverage must not
be interpreted as proof of current live-provider availability.

## Validation

- Baseline: 133 passed, one skipped.
- Final regression suite: 138 passed, one skipped. The skipped ETERNAL regression
  needs a 28 October archive absent from this checkout; no substitute was invented.
- Two real Chromium passes: 44 page loads each, with no JavaScript exceptions,
  covering eleven page paths in local API/static and desktop/mobile modes.
  Interactions exercise research, watchlist persistence, comparison prices,
  reports, screening and invalid banking inputs. This is meaningful smoke
  coverage; it does not establish that every possible company/input was tested.
- Snapshot audit passed, all inline JavaScript parsed, workflow YAML parsed, and
  Git whitespace checks passed.
- Added regression tests for all page/asset routes, null-safe facts, offline
  research, failed-BSE export preservation and retained statement provenance.

## Daily automation

Prices: weekdays at 20:00 and 22:00 IST. Fundamentals and all NSE company
profiles/statements: weekdays at 20:15 and 22:15 IST. Retrieval is paced; company
collection has a three-hour budget and reports incomplete work. Profiles retain
previously usable fields when individual sections disappear, with retained-field
metadata and separate statement retrieval dates. Both exchanges are validated
before public static exports are replaced. Failed market attempts no longer
replace the verified market-status file.

A Pages deployment workflow publishes website changes and successful automated
data refreshes. Repository Pages must use GitHub Actions as its build source.
The workflow configuration is saved; its remote provider runs and deployed site
were not verified from this environment. GitHub schedules may run late.

## Outstanding external limitations

This cloud instance denies TejHQ and Yahoo requests with proxy HTTP 403. The
required host additions are saved in the environment configuration draft. Apply
the draft in environment settings and publish the environment, then run the
refresh scripts and inspect coverage/status output. No paid credentials are
required. Do not claim all missing data was filled before successful retrieval.

GitHub Actions runs in a separate environment; its logs are the evidence for
successful scheduled updates. It checks for new facts daily, but providers may
publish statements less often, omit fields, rate-limit requests or be unavailable.
