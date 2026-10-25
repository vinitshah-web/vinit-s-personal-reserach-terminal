"""Acceptance tests for Phase 9: Five-to-Ten-Year Outlook & Fundamental Driver Tree.
Verifies Volume x Price decomposition and survivorship-corrected empirical base rates.
"""
import pytest
from src.core.longterm import LongTermOutlookEngine, DriverTreeAnalysis


def test_volume_price_driver_tree_decomposition():
    # Year 0: Rev = 1,000 Cr, Volume = 100 Lakh units -> Price = ₹100/unit
    # Year 5: Rev = 2,000 Cr, Volume = 150 Lakh units -> Price = ₹133.33/unit
    # Rev doubled in 5 years: CAGR = (2000/1000)^(1/5) - 1 = 14.87%
    # Volume: (150/100)^(1/5) - 1 = 8.45%
    # Realization: (133.33/100)^(1/5) - 1 = 5.92%
    tree = LongTermOutlookEngine.analyze_driver_tree(
        start_revenue=1000.0,
        end_revenue=2000.0,
        start_volume=100.0,
        end_volume=150.0,
        years=5
    )

    assert isinstance(tree, DriverTreeAnalysis)
    assert tree.total_revenue_cagr_pct == 14.87
    assert tree.volume_cagr_pct == 8.45
    assert tree.realization_cagr_pct == 5.92
    assert tree.driver_classification == "VOLUME_LED"
    assert 35.0 <= tree.pricing_power_score <= 45.0


def test_pricing_led_driver_tree():
    # Volume grew minimally (100 -> 110 in 5 yrs = 1.9% CAGR)
    # Price grew sharply (100 -> 160 = 9.86% CAGR)
    tree = LongTermOutlookEngine.analyze_driver_tree(
        start_revenue=1000.0,
        end_revenue=1760.0,
        start_volume=100.0,
        end_volume=110.0,
        years=5
    )
    assert tree.driver_classification == "PRICING_LED"
    assert tree.realization_cagr_pct > tree.volume_cagr_pct


def test_survivorship_corrected_base_rates():
    fmcg_rate = LongTermOutlookEngine.get_industry_compounder_base_rate("FMCG")
    assert fmcg_rate["sector"] == "FMCG"
    assert fmcg_rate["delisted_or_merged_pct"] > 10.0  # Survivorship bias explicitly accounted for
    assert fmcg_rate["pct_sustaining_15pct_cagr_10yr"] > 0.0

    banking_rate = LongTermOutlookEngine.get_industry_compounder_base_rate("BANKING")
    assert banking_rate["sector"] == "BANKING"
    assert banking_rate["delisted_or_merged_pct"] > 20.0  # Bank consolidation / distress captured

    unknown_rate = LongTermOutlookEngine.get_industry_compounder_base_rate("TEXTILES")
    assert unknown_rate["sector"] == "TEXTILES"
    assert unknown_rate["sample_size"] == 500
