"""Generates compact securities search index for both Local FastAPI & Online GitHub Pages."""
import sqlite3
import json
from pathlib import Path

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
        securities.append({
            "isin": r[0],
            "ticker": r[1],
            "name": r[2],
            "sector": r[3] or "Diversified",
            "industry": r[4] or "General",
            "series": r[5],
            "is_financial": bool(r[6])
        })
    
    out_path = Path("data/securities_search_index.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(securities, f, indent=None)
    
    print(f"Generated search index with {len(securities)} securities at {out_path} ({round(out_path.stat().st_size / 1024, 1)} KB)")

if __name__ == "__main__":
    build_index()
