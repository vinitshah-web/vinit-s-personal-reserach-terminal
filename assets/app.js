/* Shared, page-lifetime snapshot cache. Failures can be retried. */
window.AppData = (() => {
  const requests = new Map();
  async function fetchSnapshot(url, options = {}) {
    if (!requests.has(url)) {
      requests.set(url, fetch(url, {...options, signal: AbortSignal.timeout(10000)})
        .then(response => { if (!response.ok) { requests.delete(url); } return response; })
        .catch(error => { requests.delete(url); throw error; }));
    }
    return (await requests.get(url)).clone();
  }
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function quote(quotes, status, ticker, exchange = 'NSE', isin = null) {
    const row = quotes[exchange === 'BSE' ? `BSE:${ticker}` : ticker];
    const record = status.exchanges ? status.exchanges[exchange] : status;
    return row && record?.status === 'VERIFIED' && row.trade_date === record.trading_date
      && Number.isFinite(Number(row.close)) && Number(row.close) > 0
      && (!isin || !row.isin || row.isin === isin) ? row : null;
  }
  function watchlist(value) {
    if (!Array.isArray(value)) throw new Error('Watchlist must be an array.');
    if (value.length > 500) throw new Error('Import up to 500 securities at a time.');
    const unique = new Map();
    for (const item of value) {
      if (!item || typeof item.symbol !== 'string' || !/^[A-Z0-9&_.-]{1,40}$/.test(item.symbol.toUpperCase())) throw new Error('Each entry needs a valid symbol.');
      const exchange = item.exchange === 'BSE' ? 'BSE' : 'NSE';
      const row = {symbol:item.symbol.toUpperCase(), exchange, name:String(item.name || item.symbol).slice(0,200), sector:String(item.sector || '').slice(0,100), added_at:typeof item.added_at === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(item.added_at) ? item.added_at : new Date().toISOString()};
      unique.set(`${exchange}:${row.symbol}`, row);
    }
    return [...unique.values()];
  }
  return {fetch:fetchSnapshot, escape, quote, watchlist};
})();
document.addEventListener('DOMContentLoaded', () => {
  for (const nav of document.querySelectorAll('header nav')) {
    for (const [href, text] of [['valuation_lab.html','Valuation'],['quant_lab.html','Screener'],['data_quality.html','Data quality']]) {
      if (!nav.querySelector(`a[href="${href}"]`)) {
        const a = document.createElement('a'); a.href = href; a.textContent = text; a.className = 'px-3 py-1.5 rounded-md'; nav.append(a);
      }
    }
    nav.setAttribute('aria-label', 'Main navigation');
  }
  for (const input of document.querySelectorAll('input')) {
    if (!input.labels?.length && !input.hasAttribute('aria-label')) input.setAttribute('aria-label', input.placeholder || input.id || input.type);
  }
});
