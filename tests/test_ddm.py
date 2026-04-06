"""
Tests for the Dividend Discount Model valuation engine.
Verifies applicability checks and math calculations.
"""
import pandas as pd
import pytest
from src.valuation.ddm import DDMValuation


class TestCheckDDMApplicability:
    """Tests for DDM applicability checks."""

    def test_no_dividends_raises(self):
        """Company with no dividends should raise ValueError."""
        ddm = DDMValuation()
        dividend_data = {
            "has_dividends": False,
            "annual_dividend": 0.0,
            "dividend_yield": 0.0,
            "payout_ratio": 0.0,
        }
        with pytest.raises(ValueError, match="does not pay dividends"):
            ddm.check_ddm_applicability("META", dividend_data)

    def test_low_yield_raises(self):
        """Company with dividend yield below 1% should raise ValueError."""
        ddm = DDMValuation()
        dividend_data = {
            "has_dividends": True,
            "annual_dividend": 1.0,
            "dividend_yield": 0.004,  # 0.4% — too low
            "payout_ratio": 0.15,
        }
        with pytest.raises(ValueError, match="too low"):
            ddm.check_ddm_applicability("AAPL", dividend_data)

    def test_valid_dividend_company_passes(self):
        """Company with good dividends should not raise."""
        ddm = DDMValuation()
        dividend_data = {
            "has_dividends": True,
            "annual_dividend": 5.2,
            "dividend_yield": 0.032,  # 3.2% — good yield
            "payout_ratio": 0.45,
        }
        # Should not raise
        ddm.check_ddm_applicability("JNJ", dividend_data)


class TestProjectDividends:
    """Tests for dividend projection logic."""

    def test_dividends_grow(self):
        """Projected dividends should be higher than current."""
        ddm = DDMValuation()
        projected = ddm.project_dividends(
            current_dividend=5.0,
            growth_rate=0.06,
            years=5
        )
        assert len(projected) == 5
        assert projected[0] > 5.0
        assert projected[4] > projected[0]

    def test_constant_growth(self):
        """Each year should grow by growth rate."""
        ddm = DDMValuation()
        projected = ddm.project_dividends(
            current_dividend=10.0,
            growth_rate=0.10,
            years=3
        )
        assert projected[0] == pytest.approx(11.0, abs=0.01)
        assert projected[1] == pytest.approx(12.1, abs=0.01)
        assert projected[2] == pytest.approx(13.31, abs=0.01)

    def test_zero_growth(self):
        """Zero growth rate should keep dividends constant."""
        ddm = DDMValuation()
        projected = ddm.project_dividends(
            current_dividend=5.0,
            growth_rate=0.0,
            years=5
        )
        for div in projected:
            assert div == pytest.approx(5.0, abs=0.01)


class TestCalculateTerminalValue:
    """Tests for Gordon Growth Model terminal value."""

    def test_basic_terminal_value(self):
        """Terminal value should be positive."""
        ddm = DDMValuation()
        tv = ddm.calculate_terminal_value(
            final_dividend=6.0,
            cost_of_equity=0.09,
            terminal_growth_rate=0.02
        )
        # TV = 6.0 * (1 + 0.02) / (0.09 - 0.02) = 6.12 / 0.07 = 87.43
        assert tv == pytest.approx(87.43, abs=0.1)

    def test_cost_of_equity_must_exceed_growth(self):
        """Should raise if cost of equity <= terminal growth rate."""
        ddm = DDMValuation()
        with pytest.raises(ValueError):
            ddm.calculate_terminal_value(
                final_dividend=6.0,
                cost_of_equity=0.02,
                terminal_growth_rate=0.03
            )


class TestCalculateDividendGrowthRate:
    """Tests for historical dividend growth rate calculation."""

    def test_growing_dividends(self):
        """Growing dividend history should return positive CAGR."""
        ddm = DDMValuation()
        dates = pd.date_range(start="2019-01-01", periods=20, freq="QE")
        # Dividends growing from 1.0 to ~1.5 over 5 years
        values = [1.0 + i * 0.025 for i in range(20)]
        history = pd.Series(values, index=dates)

        growth_rate, source = ddm._calculate_dividend_growth_rate(history)
        assert growth_rate > 0
        assert "CAGR" in source

    def test_empty_history_returns_fallback(self):
        """Empty history should return 5% fallback."""
        ddm = DDMValuation()
        history = pd.Series(dtype=float)
        growth_rate, source = ddm._calculate_dividend_growth_rate(history)
        assert growth_rate == 0.05
        assert "fallback" in source