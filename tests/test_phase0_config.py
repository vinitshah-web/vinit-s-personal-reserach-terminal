"""Tests for Phase 0: Configuration and provenance validation."""
import pytest
from src.config_loader import ConfigLoader, ConfigValidationError


def test_config_loader_tax_rules(config):
    """Asserts that config loads and validates the provenance of all tax parameters."""
    assert "gst" in config
    assert "tax_regimes" in config
    gst = config["gst"]
    assert gst["rate"] == 0.18
    assert "source_url" in gst
    assert gst["verification_status"] == "verified"

    # Check regimes
    regimes = config["tax_regimes"]
    assert len(regimes) >= 2
    eras = [r["era"] for r in regimes]
    assert "it_act_1961" in eras
    assert "it_act_2025" in eras


def test_every_parameter_has_verification_status(config):
    """Anti-hallucination check: Every rate must have verification_status and effective_from."""
    for regime in config["tax_regimes"]:
        rules = regime["rules"]
        for rule_name, rule_body in rules.items():
            if "rates" in rule_body:
                for rate_entry in rule_body["rates"]:
                    assert "effective_from" in rate_entry
                    assert rate_entry["verification_status"] in ("verified", "unverified")
                    assert "source_url" in rate_entry


def test_invalid_config_raises():
    """Validates that missing essential fields in config raises ConfigValidationError."""
    loader = ConfigLoader()
    with pytest.raises(ConfigValidationError):
        loader._validate_tax_rules({"gst": {}})
