"""
Tests for shared financial calculations.
Verifies CAPM, terminal growth rate, and ERP calculations.
"""
import pytest
from src.utils.calculations import (
    calculate_cost_of_equity,
    get_terminal_growth_rate,
    get_equity_risk_premium,
)


class TestCalculateCostOfEquity:
    """Tests for CAPM: Re = Rf + Beta x ERP"""

    def test_basic_capm(self):
        """Standard CAPM calculation."""
        beta = 1.0
        rfr = 0.04
        erp = 0.05
        result = calculate_cost_of_equity(beta, rfr, erp)
        assert result == pytest.approx(0.09, abs=0.001)

    def test_high_beta(self):
        """High beta stock should have higher cost of equity."""
        result = calculate_cost_of_equity(beta=1.5, risk_free_rate=0.04, equity_risk_premium=0.05)
        assert result == pytest.approx(0.115, abs=0.001)

    def test_low_beta(self):
        """Low beta stock should have lower cost of equity."""
        result = calculate_cost_of_equity(beta=0.5, risk_free_rate=0.04, equity_risk_premium=0.05)
        assert result == pytest.approx(0.065, abs=0.001)

    def test_zero_beta(self):
        """Zero beta — cost of equity equals risk free rate."""
        result = calculate_cost_of_equity(beta=0.0, risk_free_rate=0.04, equity_risk_premium=0.05)
        assert result == pytest.approx(0.04, abs=0.001)


class TestGetTerminalGrowthRate:
    """Tests for terminal growth rate derivation from Treasury yield."""

    def test_normal_rate(self):
        """Normal Treasury yield gives reasonable terminal growth."""
        tgr, source = get_terminal_growth_rate(0.04)
        assert tgr == pytest.approx(0.02, abs=0.001)
        assert "Treasury" in source

    def test_floor(self):
        """Very low Treasury yield should be floored at 1.5%."""
        tgr, _ = get_terminal_growth_rate(0.01)
        assert tgr >= 0.015

    def test_cap(self):
        """Very high Treasury yield should be capped at 3.5%."""
        tgr, _ = get_terminal_growth_rate(0.10)
        assert tgr <= 0.035

    def test_returns_tuple(self):
        """Should return (value, source) tuple."""
        result = get_terminal_growth_rate(0.04)
        assert isinstance(result, tuple)
        assert len(result) == 2


class TestGetEquityRiskPremium:
    """Tests for ERP calculation."""

    def test_us_company(self):
        """US company should have zero country risk premium."""
        erp, source = get_equity_risk_premium(0.04, "United States")
        assert erp > 0
        assert "United States" in source

    def test_unknown_country_falls_back_to_us(self):
        """Unknown country should fall back to United States."""
        erp_us, _ = get_equity_risk_premium(0.04, "United States")
        erp_unknown, _ = get_equity_risk_premium(0.04, "Nonexistent Country XYZ")
        assert erp_us == erp_unknown

    def test_returns_tuple(self):
        """Should return (value, source) tuple."""
        result = get_equity_risk_premium(0.04, "United States")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_erp_reasonable_range(self):
        """ERP should be between 2% and 15%."""
        erp, _ = get_equity_risk_premium(0.04, "United States")
        assert 0.02 <= erp <= 0.15