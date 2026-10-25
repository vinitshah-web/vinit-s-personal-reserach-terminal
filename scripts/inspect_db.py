import sqlite3

conn = sqlite3.connect("data/nse_platform.db")
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(security);")
cols = cursor.fetchall()
print("Columns in security:")
for c in cols:
    print(" ", c)

cursor.execute("SELECT isin, ticker_current, company_name, sector, series, is_financial FROM security LIMIT 10;")
print("\nSample securities:")
for r in cursor.fetchall():
    print(" ", r)
