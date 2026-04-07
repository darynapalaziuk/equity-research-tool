"""
Tests for the DCF valuation engine.
Tests the full valuation run with known inputs.
"""
import pandas as pd
import pytest

from src.valuation.dcf import DCFValuation


def make_income_df():
    return pd.DataFrame(
        {
            "Total Revenue": [400e9, 375e9, 350e9],
            "Gross Profit": [170e9, 160e9, 150e9],
            "EBITDA": [130e9, 120e9, 110e9],
            "EBIT": [110e9, 100e9, 90e9],
            "Interest Expense": [-4e9, -3.5e9, -3e9],
            "Tax Provision": [15e9, 14e9, 13e9],
            "Pretax Income": [115e9, 105e9, 95e9],
            "Net Income": [100e9, 90e9, 80e9],
        }
    )


def make_balance_df():
    return pd.DataFrame(
        {
            "Total Debt": [120e9, 110e9, 100e9],
            "Cash And Cash Equivalents": [30e9, 25e9, 20e9],
            "Stockholders Equity": [80e9, 75e9, 70e9],
        }
    )


def make_cashflow_df():
    return pd.DataFrame(
        {
            "Operating Cash Flow": [110e9, 100e9, 90e9],
            "Capital Expenditure": [-10e9, -9e9, -8e9],
            "Free Cash Flow": [100e9, 91e9, 82e9],
        }
    )


def run_dcf(scenario="base"):
    dcf = DCFValuation()
    return dcf.run(
        ticker="TEST",
        income_df=make_income_df(),
        cash_flow_df=make_cashflow_df(),
        balance_sheet_df=make_balance_df(),
        beta=1.1,
        risk_free_rate=0.0431,
        shares_outstanding=15e9,
        current_price=50.0,
        country="United States",
        scenario=scenario,
    )


class TestDCFResult:
    def test_result_has_required_keys(self):
        result = run_dcf()
        assert "dcf_price_target" in result
        assert "wacc" in result
        assert "cost_of_equity" in result
        assert "cost_of_debt" in result
        assert "tax_rate" in result
        assert "terminal_value" in result
        assert "projected_fcf" in result
        assert "historical_fcf" in result

    def test_price_target_positive(self):
        result = run_dcf()
        assert result["dcf_price_target"] > 0

    def test_wacc_reasonable_range(self):
        result = run_dcf()
        assert 0.04 <= result["wacc"] <= 0.15

    def test_five_year_projection(self):
        result = run_dcf()
        assert len(result["projected_fcf"]) == 5

    def test_terminal_value_positive(self):
        result = run_dcf()
        assert result["terminal_value"] > 0

    def test_cost_of_equity_above_risk_free(self):
        result = run_dcf()
        assert result["cost_of_equity"] > 0.0431

    def test_best_scenario_higher_than_base(self):
        base = run_dcf("base")
        best = run_dcf("best")
        assert best["dcf_price_target"] > base["dcf_price_target"]

    def test_worst_scenario_lower_than_base(self):
        base = run_dcf("base")
        worst = run_dcf("worst")
        assert worst["dcf_price_target"] < base["dcf_price_target"]

    def test_data_sources_documented(self):
        result = run_dcf()
        assert "equity_risk_premium" in result["inputs"]
        assert "terminal_growth_rate" in result["inputs"]
