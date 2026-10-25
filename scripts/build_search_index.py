"""Generates compact securities search index for both Local FastAPI & Online GitHub Pages."""
import sqlite3
import json
from pathlib import Path

ALIASES = {
    "ETERNAL": ["ZOMATO", "BLINKIT", "HYPERPURE"],
    "ONE97": ["PAYTM"],
    "LT": ["L&T", "LARSEN & TOUBRO"],
    "M&M": ["MAHINDRA", "MAHINDRA & MAHINDRA"],
    "TATAMOTORS": ["TML", "JLR"],
    "RELIANCE": ["RIL", "JIO"],
    "HDFCBANK": ["HDFC"]
}

SECTOR_MAPPINGS = {
    "ETERNAL": ("Consumer Cyclical", "Internet Retail - Quick Commerce & Food Delivery"),
    "RELIANCE": ("Energy", "Oil & Gas Refining, Petrochemicals & Retail"),
    "TCS": ("Technology", "IT Services & Enterprise Consulting"),
    "HDFCBANK": ("Financial Services", "Private Sector Commercial Banking"),
    "INFY": ("Technology", "IT Services & Digital Transformation"),
    "PERSISTENT": ("Technology", "Digital Engineering & Enterprise Modernization")
}

def build_index():
    db_path = Path("data/nse_platform.db")
    if not db_path.exists():
        print("Database not found!")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT isin, ticker_current, company_name, sector, industry, series, is_financial 
        FROM security
        ORDER BY ticker_current ASC;
    """)
    rows = cur.fetchall()
    
    securities = []
    for r in rows:
        ticker = r[1]
        sector = r[3]
        industry = r[4]
        if ticker in SECTOR_MAPPINGS:
            sector, industry = SECTOR_MAPPINGS[ticker]

        sec_entry = {
            "isin": r[0],
            "ticker": ticker,
            "name": r[2],
            "sector": sector or "Diversified",
            "industry": industry or "General",
            "series": r[5],
            "is_financial": bool(r[6])
        }
        if ticker in ALIASES:
            sec_entry["aliases"] = ALIASES[ticker]
        securities.append(sec_entry)
    
    out_path = Path("data/securities_search_index.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(securities, f, indent=None)
    
    print(f"Generated search index with {len(securities)} securities at {out_path} ({round(out_path.stat().st_size / 1024, 1)} KB)")

if __name__ == "__main__":
    build_index()
