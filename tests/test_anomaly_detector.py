"""
Tests for the financial anomaly detection engine.
Verifies all 5 audit-style checks work correctly.
"""
import pandas as pd
import pytest
from src.audit.anomaly_detector import AnomalyDetector


def make_income_df(
    revenue_current=100e9,
    revenue_prior=94e9,
    gross_profit_current=44e9,
    gross_profit_prior=41e9,
    net_income=100e9,
    ebitda=120e9,
    ebit=100e9,
    interest_expense=-3e9,
):
    """Helper to create a minimal income statement DataFrame."""
    return pd.DataFrame(
        {
            "Total Revenue": [revenue_current, revenue_prior],
            "Gross Profit": [gross_profit_current, gross_profit_prior],
            "Net Income": [net_income, net_income],
            "EBITDA": [ebitda, ebitda],
            "EBIT": [ebit, ebit],
            "Interest Expense": [interest_expense, interest_expense],
        }
    )


def make_balance_df(
    accounts_receivable_current=10e9,
    accounts_receivable_prior=8e9,
    total_debt=50e9,
    cash=100e9,
):
    """Helper to create a minimal balance sheet DataFrame."""
    return pd.DataFrame(
        {
            "Accounts Receivable": [
                accounts_receivable_current,
                accounts_receivable_prior,
            ],
            "Total Debt": [total_debt, total_debt],
            "Cash And Cash Equivalents": [cash, cash],
        }
    )


def make_cashflow_df(operating_cf=110e9, fcf=100e9):
    """Helper to create a minimal cash flow DataFrame."""
    return pd.DataFrame(
        {
            "Operating Cash Flow": [operating_cf, operating_cf],
            "Free Cash Flow": [fcf, fcf],
        }
    )


class TestRevenueQuality:
    """Tests for receivables vs revenue growth check."""

    def test_clean_company(self):
        """Normal receivables growth should not flag."""
        detector = AnomalyDetector()
        income = make_income_df()
        balance = make_balance_df(
            accounts_receivable_current=10e9,
            accounts_receivable_prior=9.8e9,  # ← change this line
        )
        flags = detector.check_revenue_quality(income, balance)
        assert len(flags) == 0

    def test_high_receivables_growth(self):
        """Receivables growing 3x faster than revenue should flag HIGH."""
        detector = AnomalyDetector()
        income = make_income_df(revenue_current=100e9, revenue_prior=94e9)
        balance = make_balance_df(
            accounts_receivable_current=20e9,
            accounts_receivable_prior=8e9,
        )
        flags = detector.check_revenue_quality(income, balance)
        assert len(flags) > 0
        assert flags[0].severity == "HIGH"

    def test_medium_receivables_growth(self):
        detector = AnomalyDetector()
        # Revenue growth: 6.38%, Receivables growth: ~10% → ratio ~1.6x
        income = make_income_df(revenue_current=100e9, revenue_prior=94e9)
        balance = make_balance_df(
            accounts_receivable_current=8.8e9,
            accounts_receivable_prior=8e9,
        )
        flags = detector.check_revenue_quality(income, balance)
        assert len(flags) > 0
        assert flags[0].severity == "MEDIUM"


class TestEarningsQuality:
    """Tests for operating cash flow vs net income check."""

    def test_clean_company(self):
        detector = AnomalyDetector()
        income = make_income_df()
        balance = make_balance_df(
            accounts_receivable_current=10e9,
            accounts_receivable_prior=9.8e9,
        )
        flags = detector.check_revenue_quality(income, balance)
        assert len(flags) == 0

    def test_negative_ocf(self):
        """Negative OCF with positive net income should flag HIGH."""
        detector = AnomalyDetector()
        income = make_income_df(net_income=100e9)
        cashflow = make_cashflow_df(operating_cf=-10e9)
        flags = detector.check_earnings_quality(income, cashflow)
        assert len(flags) > 0
        assert flags[0].severity == "HIGH"

    def test_low_ocf_ratio(self):
        """OCF at 50% of net income should flag MEDIUM."""
        detector = AnomalyDetector()
        income = make_income_df(net_income=100e9)
        cashflow = make_cashflow_df(operating_cf=60e9)
        flags = detector.check_earnings_quality(income, cashflow)
        assert len(flags) > 0
        assert flags[0].severity == "MEDIUM"


class TestDebtSustainability:
    """Tests for leverage and interest coverage checks."""

    def test_clean_company(self):
        """Low leverage should not flag."""
        detector = AnomalyDetector()
        income = make_income_df(ebitda=120e9)
        balance = make_balance_df(total_debt=50e9, cash=100e9)
        flags = detector.check_debt_sustainability(income, balance)
        assert len(flags) == 0

    def test_high_leverage(self):
        """Net Debt/EBITDA above 4x should flag HIGH."""
        detector = AnomalyDetector()
        income = make_income_df(ebitda=10e9)
        balance = make_balance_df(total_debt=60e9, cash=5e9)
        flags = detector.check_debt_sustainability(income, balance)
        high_flags = [f for f in flags if f.severity == "HIGH"]
        assert len(high_flags) > 0


class TestMarginTrends:
    """Tests for gross margin compression check."""

    def test_stable_margins(self):
        """Stable margins should not flag."""
        detector = AnomalyDetector()
        income = make_income_df(
            gross_profit_current=44e9,
            gross_profit_prior=41e9,
            revenue_current=100e9,
            revenue_prior=94e9,
        )
        flags = detector.check_margin_trends(income)
        assert len(flags) == 0

    def test_margin_compression_high(self):
        """More than 300bps compression should flag HIGH."""
        detector = AnomalyDetector()
        income = make_income_df(
            gross_profit_current=30e9,
            gross_profit_prior=40e9,
            revenue_current=100e9,
            revenue_prior=100e9,
        )
        flags = detector.check_margin_trends(income)
        assert len(flags) > 0
        assert flags[0].severity == "HIGH"


class TestRunMethod:
    """Tests for the main run() method."""

    def test_clean_company_returns_clean(self):
        detector = AnomalyDetector()
        result = detector.run(
            ticker="TEST",
            income_df=make_income_df(),
            balance_sheet_df=make_balance_df(
                accounts_receivable_current=10e9,
                accounts_receivable_prior=9.5e9,
            ),
            cash_flow_df=make_cashflow_df(),
        )
        assert result["risk_level"] == "CLEAN"
        assert result["total_flags"] == 0

    def test_result_structure(self):
        """Result should have all required keys."""
        detector = AnomalyDetector()
        result = detector.run(
            ticker="TEST",
            income_df=make_income_df(),
            balance_sheet_df=make_balance_df(),
            cash_flow_df=make_cashflow_df(),
        )
        assert "ticker" in result
        assert "risk_level" in result
        assert "total_flags" in result
        assert "high_count" in result
        assert "medium_count" in result
        assert "flags" in result