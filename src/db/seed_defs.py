"""Standard Financial Line Item Definitions seeder.
Populates standard line_item_def records for non-financial and financial entities.
"""
from typing import List, Dict
from sqlalchemy.orm import Session
from src.db.models import LineItemDef

STANDARD_LINE_ITEMS = [
    # Flow items
    {"item_code": "REV", "item_name": "Revenue from Operations", "category": "INCOME", "applicable_to": "ALL", "unit_type": "CURRENCY"},
    {"item_code": "EBITDA", "item_name": "Operating Profit / EBITDA", "category": "INCOME", "applicable_to": "NON_FINANCIAL", "unit_type": "CURRENCY"},
    {"item_code": "EBIT", "item_name": "Operating Income / EBIT", "category": "INCOME", "applicable_to": "NON_FINANCIAL", "unit_type": "CURRENCY"},
    {"item_code": "PAT", "item_name": "Profit After Tax / Net Income", "category": "INCOME", "applicable_to": "ALL", "unit_type": "CURRENCY"},
    {"item_code": "CFO", "item_name": "Cash Flow from Operations", "category": "CASH_FLOW", "applicable_to": "ALL", "unit_type": "CURRENCY"},
    {"item_code": "INT_EXP", "item_name": "Finance Costs / Interest Expense", "category": "INCOME", "applicable_to": "ALL", "unit_type": "CURRENCY"},
    {"item_code": "DEP_AMORT", "item_name": "Depreciation & Amortization", "category": "INCOME", "applicable_to": "ALL", "unit_type": "CURRENCY"},
    {"item_code": "TAX_EXP", "item_name": "Tax Expense", "category": "INCOME", "applicable_to": "ALL", "unit_type": "CURRENCY"},
    
    # Balance sheet items
    {"item_code": "TOTAL_DEBT", "item_name": "Total Debt (Short & Long Term)", "category": "BALANCE_SHEET", "applicable_to": "NON_FINANCIAL", "unit_type": "CURRENCY"},
    {"item_code": "CASH_EQUIV", "item_name": "Cash and Cash Equivalents", "category": "BALANCE_SHEET", "applicable_to": "ALL", "unit_type": "CURRENCY"},
    {"item_code": "TOTAL_EQUITY", "item_name": "Total Shareholders Equity", "category": "BALANCE_SHEET", "applicable_to": "ALL", "unit_type": "CURRENCY"},
    {"item_code": "TOTAL_ASSETS", "item_name": "Total Assets", "category": "BALANCE_SHEET", "applicable_to": "ALL", "unit_type": "CURRENCY"},

    # Banking specific items
    {"item_code": "INT_EARNED", "item_name": "Interest Earned", "category": "INCOME", "applicable_to": "FINANCIAL", "unit_type": "CURRENCY"},
    {"item_code": "INT_EXPENDED", "item_name": "Interest Expended", "category": "INCOME", "applicable_to": "FINANCIAL", "unit_type": "CURRENCY"},
    {"item_code": "AVG_EARNING_ASSETS", "item_name": "Average Earning Assets", "category": "BALANCE_SHEET", "applicable_to": "FINANCIAL", "unit_type": "CURRENCY"},
    {"item_code": "CASA_DEPOSITS", "item_name": "Current & Savings Account Deposits", "category": "BALANCE_SHEET", "applicable_to": "FINANCIAL", "unit_type": "CURRENCY"},
    {"item_code": "TOTAL_DEPOSITS", "item_name": "Total Deposits", "category": "BALANCE_SHEET", "applicable_to": "FINANCIAL", "unit_type": "CURRENCY"},
    {"item_code": "GROSS_NPA", "item_name": "Gross Non-Performing Assets", "category": "ASSET_QUALITY", "applicable_to": "FINANCIAL", "unit_type": "CURRENCY"},
    {"item_code": "GROSS_ADVANCES", "item_name": "Gross Total Advances", "category": "ASSET_QUALITY", "applicable_to": "FINANCIAL", "unit_type": "CURRENCY"},
]


def seed_standard_line_items(session: Session) -> int:
    """Populates standard line items if they don't already exist."""
    count = 0
    for defn in STANDARD_LINE_ITEMS:
        existing = session.query(LineItemDef).filter(LineItemDef.item_code == defn["item_code"]).first()
        if not existing:
            item = LineItemDef(
                item_code=defn["item_code"],
                item_name=defn["item_name"],
                category=defn["category"],
                applicable_to=defn["applicable_to"],
                unit_type=defn["unit_type"],
                description=defn.get("description")
            )
            session.add(item)
            count += 1
    session.commit()
    return count
