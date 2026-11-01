"""Regression tests for audited page routing and missing-data handling."""
from fastapi.testclient import TestClient
from src.api.main import app, merge_available_fundamentals
from src.ingestion.providers import FinancialsAdapter


def test_all_pages_and_shared_assets_are_served():
    with TestClient(app) as client:
        for page in ('index','research','compare','watchlist','reports','valuation_lab','quant_lab','data_quality','stock_intelligence'):
            response = client.get(f'/{page}.html')
            assert response.status_code == 200, page
        assert client.get('/assets/app.js').status_code == 200
        assert client.get('/assets/tailwind.css').status_code == 200
        assert client.get('/not-a-page.html').status_code == 404


def test_null_batch_values_preserve_existing_facts_without_mutating_cache():
    cached = {'shares_outstanding_cr': 42, 'business_summary': 'Sourced overview', 'pb_ratio': 2}
    merged = merge_available_fundamentals(cached, {'shares_outstanding_cr': None, 'pe_ratio': 12, 'pb_ratio': None, 'pb_ratio_reason':'No dated equity'})
    assert merged['shares_outstanding_cr'] == 42
    assert merged['business_summary'] == 'Sourced overview'
    assert merged['pe_ratio'] == 12
    assert merged['pb_ratio'] is None
    assert cached['pb_ratio'] == 2


def test_uncached_research_does_not_trigger_slow_live_financial_requests(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(FinancialsAdapter, '_CACHE', {})
    def unexpected(*args, **kwargs):
        raise AssertionError('Interactive research must not call Yahoo')
    monkeypatch.setattr('src.ingestion.providers.yf.Ticker', unexpected)
    dossier = FinancialsAdapter.get_company_dossier('MISSING')
    assert dossier['has_statements'] is False
    assert dossier['business_summary'] is None


def test_failed_bse_refresh_preserves_complete_static_set(monkeypatch, tmp_path, db_session):
    from types import SimpleNamespace
    from scripts import refresh_market_data as refresh
    monkeypatch.chdir(tmp_path)
    data = tmp_path / 'data'
    data.mkdir()
    originals = {name: '{"previous":"verified"}' for name in ('latest_quotes.json','market_data_status.json','securities_search_index.json')}
    for name, text in originals.items():
        (data / name).write_text(text)
    monkeypatch.setattr(refresh, 'parse_args', lambda: SimpleNamespace(export_static=True, minimum_coverage=1000, maximum_status_age_days=7))
    monkeypatch.setattr(refresh, 'get_session_factory', lambda: lambda: db_session)
    monkeypatch.setattr(refresh, 'refresh_nse_snapshot', lambda *args, **kwargs: SimpleNamespace(trading_date='2026-10-30'))
    def unavailable(**kwargs):
        raise RuntimeError('BSE provider unavailable')
    monkeypatch.setattr(refresh, 'fetch_exchange_snapshot', unavailable)
    assert refresh.main() == 1
    for name, text in originals.items():
        assert (data / name).read_text() == text


def test_partial_profile_refresh_preserves_previous_statements(monkeypatch, tmp_path):
    import json
    import pandas as pd
    from types import SimpleNamespace
    monkeypatch.chdir(tmp_path)
    cache = tmp_path / 'data/dossier_cache'
    cache.mkdir(parents=True)
    (cache / 'ABC.json').write_text(json.dumps({'financial_statements':[{'period':'FY25','revenue_cr':100}], 'retrieval_time':'2026-01-01', 'shares_outstanding_cr':2}))
    ticker = SimpleNamespace(info={'longBusinessSummary':'Updated sourced description'}, financials=pd.DataFrame(), balance_sheet=pd.DataFrame(), cashflow=pd.DataFrame())
    monkeypatch.setattr('src.ingestion.providers.yf.Ticker', lambda *args: ticker)
    monkeypatch.setattr(FinancialsAdapter, '_CACHE', {})
    row = FinancialsAdapter.get_company_dossier('ABC', allow_live=True)
    assert row['business_summary'] == 'Updated sourced description'
    assert row['financial_statements'][0]['revenue_cr'] == 100
    assert row['statements_retrieved_at'] == '2026-01-01'
    assert row['shares_outstanding_cr'] == 2
    assert row['pb_ratio'] is None
    assert 'financial_statements' in row['retained_fields']
