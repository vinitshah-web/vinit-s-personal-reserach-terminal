"""Indian Tax Engine supporting dual-era statutes:
- Income-tax Act, 1961 (< 2026-04-01)
- Income-tax Act, 2025 (>= 2026-04-01)
"""
from datetime import date
from typing import Any, Dict, List, Optional
from src.config_loader import ConfigLoader


class UnverifiedRateError(Exception):
    """Raised when an unverified statutory rate is used without opt-in."""
    pass


class TaxEngine:
    def __init__(self, config: Optional[Dict[str, Any]] = None, allow_unverified: bool = False):
        if config is None:
            loader = ConfigLoader()
            self.config = loader.load_tax_rules()
        else:
            self.config = config
        self.allow_unverified = allow_unverified
        self.transition_cutover = date(2026, 4, 1)

    def get_regime_for_date(self, event_date: date) -> Dict[str, Any]:
        """Resolves whether IT Act 1961 or IT Act 2025 governs the transaction."""
        for regime in self.config["tax_regimes"]:
            app_from = date.fromisoformat(regime["applicable_from"])
            app_to = date.fromisoformat(regime["applicable_to"]) if regime.get("applicable_to") else None

            if app_to:
                if app_from <= event_date <= app_to:
                    return regime
            else:
                if app_from <= event_date:
                    return regime
        raise ValueError(f"No tax regime found for date: {event_date}")

    def calculate_stt_delivery(self, buy_turnover: float, sell_turnover: float) -> Dict[str, float]:
        """Calculates Securities Transaction Tax on delivery trades (0.1% on buy & sell turnover)."""
        rate = 0.001
        stt_buy = round(buy_turnover * rate, 2)
        stt_sell = round(sell_turnover * rate, 2)
        return {
            "stt_buy": stt_buy,
            "stt_sell": stt_sell,
            "total_stt": round(stt_buy + stt_sell, 2)
        }

    def calculate_stamp_duty_delivery(self, buy_turnover: float) -> float:
        """Calculates Stamp Duty on equity delivery purchase (0.015% on buy leg only)."""
        rate = self.config["stamp_duty"]["rate_delivery_buy"]
        return round(buy_turnover * rate, 2)

    def calculate_gst(
        self,
        brokerage: float,
        exchange_charges: float = 0.0,
        sebi_fees: float = 0.0,
        dp_charges: float = 0.0
    ) -> float:
        """Calculates 18% GST on services. STT and Stamp Duty are strictly excluded from the base."""
        gst_cfg = self.config["gst"]
        if gst_cfg["verification_status"] != "verified" and not self.allow_unverified:
            raise UnverifiedRateError("GST rate is unverified.")
        
        taxable_base = brokerage + exchange_charges + sebi_fees + dp_charges
        return round(taxable_base * gst_cfg["rate"], 2)

    def calculate_dividend_tds(
        self,
        gross_dividend: float,
        payment_date: date,
        is_individual: bool = True,
        has_valid_pan: bool = True,
        is_cash_payment: bool = False
    ) -> Dict[str, Any]:
        """
        Calculates dividend Tax Deducted at Source (TDS) under:
        - IT Act 1961: Section 194 & Section 206AA
        - IT Act 2025: Section 393(1) Table (Sl. No. 7) & Section 397(2)

        Threshold rules:
        - Resident Individual: ₹10,000 threshold per company per year (from FY 25-26 / 2025 Act).
        - If payment is made in cash, no threshold exemption applies.
        - Corporate / Firm / Non-individual: Threshold is STRICTLY NIL (deduction from Rupee 1).
        - Failure to furnish valid PAN: Deduction at 20% under Section 397(2) (or Sec 206AA).
        """
        regime = self.get_regime_for_date(payment_date)
        era = regime["era"]
        tds_rules = regime["rules"]["dividend_tds"]
        section = tds_rules["section"]
        no_pan_section = tds_rules["no_pan_section"]

        rate_obj = self._find_rate_object_for_date(tds_rules["rates"], payment_date)
        
        if not has_valid_pan:
            applicable_rate = rate_obj["rate_without_pan"]  # 20%
            threshold = 0.0  # Penal withholding applies without threshold exemption
            governing_sec = no_pan_section
        else:
            applicable_rate = rate_obj["rate_resident_individual_with_pan"] if is_individual else rate_obj["rate_corporate_with_pan"]
            if is_individual and not is_cash_payment:
                threshold = rate_obj["threshold_individual"]
            else:
                threshold = 0.0  # Corporate or cash payment has nil threshold
            governing_sec = section

        if gross_dividend > threshold:
            tds_deducted = round(gross_dividend * applicable_rate, 2)
        else:
            tds_deducted = 0.0

        net_dividend = round(gross_dividend - tds_deducted, 2)

        return {
            "era": era,
            "governing_section": governing_sec,
            "is_individual": is_individual,
            "has_valid_pan": has_valid_pan,
            "gross_dividend": gross_dividend,
            "threshold_applied": threshold,
            "tds_rate": applicable_rate,
            "tds_deducted": tds_deducted,
            "net_dividend_payable": net_dividend
        }

    def calculate_equity_capital_gains(
        self,
        buy_date: date,
        buy_price: float,
        sell_date: date,
        sell_price: float,
        quantity: int,
        cumulative_prior_ltcg_in_period: float = 0.0
    ) -> Dict[str, Any]:
        """
        Calculates capital gains tax for listed equity with STT paid.
        Enforces holding period boundary (12 months = 365 days) and dual-era statutory provisions.
        """
        holding_days = (sell_date - buy_date).days
        gross_gain = round((sell_price - buy_price) * quantity, 2)
        regime = self.get_regime_for_date(sell_date)
        era = regime["era"]
        rules = regime["rules"]

        is_long_term = holding_days > 365

        if not is_long_term:
            # Short-Term Capital Gains
            stcg_rule = rules["stcg_equity"]
            section = stcg_rule["section"]
            rate = self._find_rate_for_date(stcg_rule["rates"], sell_date)
            taxable_gain = max(0.0, gross_gain)
            tax_payable = round(taxable_gain * rate, 2) if gross_gain > 0 else 0.0
            return {
                "gain_type": "STCG",
                "era": era,
                "governing_section": section,
                "holding_days": holding_days,
                "gross_gain": gross_gain,
                "taxable_gain": taxable_gain,
                "tax_rate": rate,
                "tax_payable": tax_payable
            }
        else:
            # Long-Term Capital Gains
            ltcg_rule = rules["ltcg_equity"]
            section = ltcg_rule["section"]
            rate_obj = self._find_rate_object_for_date(ltcg_rule["rates"], sell_date)
            rate = rate_obj["rate"]
            annual_exemption = rate_obj["exemption_limit"]

            # Remaining exemption in this period
            remaining_exemption = max(0.0, annual_exemption - cumulative_prior_ltcg_in_period)
            taxable_gain = max(0.0, gross_gain - remaining_exemption) if gross_gain > 0 else 0.0
            tax_payable = round(taxable_gain * rate, 2) if taxable_gain > 0 else 0.0

            return {
                "gain_type": "LTCG",
                "era": era,
                "governing_section": section,
                "holding_days": holding_days,
                "gross_gain": gross_gain,
                "annual_exemption": annual_exemption,
                "exemption_utilized": min(gross_gain, remaining_exemption) if gross_gain > 0 else 0.0,
                "taxable_gain": taxable_gain,
                "tax_rate": rate,
                "tax_payable": tax_payable
            }

    def _find_rate_for_date(self, rates: List[Dict[str, Any]], target_date: date) -> float:
        rate_obj = self._find_rate_object_for_date(rates, target_date)
        return float(rate_obj["rate"])

    def _find_rate_object_for_date(self, rates: List[Dict[str, Any]], target_date: date) -> Dict[str, Any]:
        for r in rates:
            eff_from = date.fromisoformat(r["effective_from"])
            eff_to = date.fromisoformat(r["effective_to"]) if r.get("effective_to") else None
            if eff_to:
                if eff_from <= target_date <= eff_to:
                    if r.get("verification_status") != "verified" and not self.allow_unverified:
                        raise UnverifiedRateError(f"Rate for date {target_date} is unverified.")
                    return r
            else:
                if eff_from <= target_date:
                    if r.get("verification_status") != "verified" and not self.allow_unverified:
                        raise UnverifiedRateError(f"Rate for date {target_date} is unverified.")
                    return r
        raise ValueError(f"No rate found effective for date: {target_date}")
