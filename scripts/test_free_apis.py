import yfinance as yf

ticker = yf.Ticker("HDFCBANK.NS")
info = ticker.info
print("--- HDFCBANK.NS INFO ---")
print("Short Name:", info.get("shortName"))
print("Sector:", info.get("sector"))
print("Industry:", info.get("industry"))
print("Market Cap:", info.get("marketCap"))
print("Book Value:", info.get("bookValue"))
print("Price to Book:", info.get("priceToBook"))
print("Business Summary (first 150 chars):", info.get("longBusinessSummary", "")[:150])
inc = ticker.financials
print("Income Statement Available Years:", list(inc.columns) if not inc.empty else "Empty")
