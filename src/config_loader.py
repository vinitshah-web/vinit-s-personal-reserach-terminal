"""Configuration loader and validator for tax, cost, and valuation rules."""
import json
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


class ConfigLoader:
    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            # Default to <workspace_root>/config
            self.config_dir = Path(__file__).parent.parent / "config"
        else:
            self.config_dir = Path(config_dir)

    def load_tax_rules(self) -> Dict[str, Any]:
        tax_path = self.config_dir / "tax_rules.json"
        if not tax_path.exists():
            raise FileNotFoundError(f"Missing configuration file: {tax_path}")

        with open(tax_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._validate_tax_rules(data)
        return data

    def load_model_params(self) -> Dict[str, Any]:
        params_path = self.config_dir / "model_params.json"
        if not params_path.exists():
            raise FileNotFoundError(f"Missing configuration file: {params_path}")

        with open(params_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _validate_tax_rules(self, data: Dict[str, Any]) -> None:
        """Validates that every rule parameter has verification provenance."""
        # Validate GST
        gst = data.get("gst")
        if not gst or "source_url" not in gst or "effective_from" not in gst:
            raise ConfigValidationError("GST rule must include source_url and effective_from.")
        if gst.get("verification_status") not in ("verified", "unverified"):
            raise ConfigValidationError("GST rule verification_status must be 'verified' or 'unverified'.")

        # Validate Tax Regimes
        regimes = data.get("tax_regimes")
        if not regimes or not isinstance(regimes, list):
            raise ConfigValidationError("Configuration must define at least one tax regime.")

        for regime in regimes:
            if "era" not in regime or "applicable_from" not in regime or "rules" not in regime:
                raise ConfigValidationError(f"Invalid regime definition in: {regime}")
            rules = regime["rules"]
            for rule_name, rule_body in rules.items():
                if rule_name in ("stcg_equity", "ltcg_equity", "dividend_tds"):
                    rates = rule_body.get("rates", [])
                    if not rates:
                        raise ConfigValidationError(f"Rule {rule_name} in {regime['era']} has empty rates.")
                    for r in rates:
                        if "effective_from" not in r or "verification_status" not in r:
                            raise ConfigValidationError(f"Rate in {rule_name} missing effective_from or verification_status")
