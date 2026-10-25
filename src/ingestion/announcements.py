"""NSE Corporate Announcements and Event Disclosures parser.
Parses official exchange disclosure files (e.g. anDDMMYYYY.txt) for dividends,
auditor changes, postal ballots, and material SEBI LODR Regulation 30 disclosures.
"""
import re
from datetime import date, datetime
from typing import List, Dict, Any, Optional


class AnnouncementParser:
    """Parses raw text announcements from NSE PR daily archives."""

    @staticmethod
    def parse_announcements_text(text: str, event_date: date) -> List[Dict[str, Any]]:
        """
        Parses pipe/colon delimited announcement text blocks.
        Format typically:
        COMPANY NAME    SYMBOL    : CATEGORY SYMBOL : Text disclosure...
        """
        records = []
        # Pattern matching: COMPANY_NAME [space] SYMBOL [space] : CATEGORY SYMBOL : DESCRIPTION
        lines = text.strip().split("\n")
        
        current_entry = None
        for line in lines:
            line_str = line.strip()
            if not line_str or line_str.startswith("COMPANY NAME"):
                continue

            # Check if this line starts a new announcement
            match = re.match(r"^(.+?)\s+([A-Z0-9]+)\s+:\s+([^:]+?)\s+([A-Z0-9]+)\s+:\s+(.+)$", line_str)
            if match:
                if current_entry:
                    records.append(current_entry)
                
                company_name = match.group(1).strip()
                symbol = match.group(2).strip()
                category = match.group(3).strip()
                desc = match.group(5).strip()

                # Detect event type and extract metrics
                event_type = "GENERAL_LODR"
                dividend_amount = None
                severity = "INFO"

                cat_upper = category.upper()
                desc_upper = desc.upper()

                if "DIVIDEND" in cat_upper or "DIVIDEND" in desc_upper:
                    event_type = "DIVIDEND_DECLARATION"
                    # Try extracting dividend amount (e.g. "Rs. 25" or "Rs 25.00" or "Re 1")
                    div_match = re.search(r"(?:Rs\.?|INR|Re\.?)\s*([0-9]+(?:\.[0-9]+)?)", desc, re.IGNORECASE)
                    if div_match:
                        try:
                            dividend_amount = float(div_match.group(1))
                        except ValueError:
                            pass
                elif "AUDITOR" in cat_upper or "RESIGNATION" in desc_upper:
                    event_type = "AUDITOR_RESIGNATION"
                    severity = "CRITICAL"
                elif "PLEDGE" in desc_upper or "ENCUMBRANCE" in desc_upper:
                    event_type = "PROMOTER_PLEDGE"
                    severity = "HIGH"
                elif "MEETING" in cat_upper or "POSTAL BALLOT" in desc_upper:
                    event_type = "SHAREHOLDER_MEETING"

                current_entry = {
                    "trade_date": event_date,
                    "symbol": symbol,
                    "company_name": company_name,
                    "category": category,
                    "event_type": event_type,
                    "dividend_amount_per_share": dividend_amount,
                    "severity": severity,
                    "description": desc
                }
            else:
                # Continuation line
                if current_entry:
                    current_entry["description"] += " " + line_str

        if current_entry:
            records.append(current_entry)

        return records
