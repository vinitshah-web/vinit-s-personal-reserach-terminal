import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from src.ingestion.providers import FinancialsAdapter

stocks = ['DIXON', 'TRENT', 'POLYCAB', 'FEDERALBNK']
for s in stocks:
    d = FinancialsAdapter.get_company_dossier(s)
    name = d.get('company_name', s)
    periods = len(d.get('financial_statements', []))
    mcap = d.get('market_cap_cr', 0.0)
    print(f"Cached {s:10} | {name:30} | Mcap: ₹{mcap:,.1f} Cr | Statements: {periods}")
