"""
Sensitivity analysis for DCF valuation.

Shows how the price target changes across different
WACC and terminal growth rate assumptions.

Standard in professional equity research — helps readers
understand the range of outcomes and key assumptions.
"""

import pandas as pd
from src.valuation.dcf import DCFValuation


def run_sensitivity_analysis(
    ticker: str,
    income_df: pd.DataFrame,
    cash_flow_df: pd.DataFrame,
    balance_sheet_df: pd.DataFrame,
    beta: float,
    risk_free_rate: float,
    shares_outstanding: float,
    country: str,
    base_wacc: float,
    base_tgr: float,
    scenario: str = "base",
) -> pd.DataFrame:
    """
    Run DCF across a grid of WACC and terminal growth rate assumptions.

    Args:
        base_wacc: the WACC from the base DCF run
        base_tgr: the terminal growth rate from the base DCF run

    Returns:
        DataFrame with WACC as rows, TGR as columns, price targets as values
    """

    wacc_range = [
        round(base_wacc - 0.02, 4),
        round(base_wacc - 0.01, 4),
        round(base_wacc, 4),
        round(base_wacc + 0.01, 4),
        round(base_wacc + 0.02, 4),
    ]

    tgr_range = [
        round(base_tgr - 0.01, 4),
        round(base_tgr - 0.005, 4),
        round(base_tgr, 4),
        round(base_tgr + 0.005, 4),
        round(base_tgr + 0.01, 4),
    ]

    results = {}

    for tgr in tgr_range:
        col_results = {}
        for wacc in wacc_range:
            try:
                if wacc <= tgr:
                    col_results[f"{wacc:.1%}"] = None
                    continue

                dcf = DCFValuation()
                price = dcf.run_with_custom_wacc(
                    ticker=ticker,
                    income_df=income_df,
                    cash_flow_df=cash_flow_df,
                    balance_sheet_df=balance_sheet_df,
                    beta=beta,
                    risk_free_rate=risk_free_rate,
                    shares_outstanding=shares_outstanding,
                    country=country,
                    scenario=scenario,
                    custom_wacc=wacc,
                    custom_tgr=tgr,
                )
                col_results[f"{wacc:.1%}"] = round(price, 2)

            except Exception:
                col_results[f"{wacc:.1%}"] = None

        results[f"{tgr:.2%}"] = col_results

    df = pd.DataFrame(results)
    df.index.name = "WACC \\ TGR"
    return df