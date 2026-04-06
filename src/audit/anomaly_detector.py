from dataclasses import dataclass
from typing import List

import pandas as pd


@dataclass
class AnomalyFlag:
    """
    Represents a single financial anomaly detected.

    Attributes:
        flag_type: category of anomaly
        severity: LOW, MEDIUM, or HIGH
        description: human readable explanation
        metric_value: the actual number that triggered the flag
    """

    flag_type: str
    severity: str
    description: str
    metric_value: float


class AnomalyDetector:
    """
    Financial anomaly detection engine.

    Applies audit-style checks to financial statements
    to flag potential risks, manipulation, or deterioration.

    Based on real audit logic from EY Technology Risk practice:
    - Revenue quality checks
    - Earnings quality checks
    - Debt sustainability checks
    - Margin trend analysis
    - Cash conversion checks

    Each check returns a list of AnomalyFlag objects.
    Severity levels:
        HIGH   — immediate concern, materially affects valuation
        MEDIUM — worth monitoring, may affect future performance
        LOW    — minor flag, informational only
    """

    def check_revenue_quality(
        self, income_df: pd.DataFrame, balance_sheet_df: pd.DataFrame
    ) -> List[AnomalyFlag]:
        """
        Check if receivables are growing faster than revenue.

        Why this matters:
            If a company books revenue but customers aren't paying,
            receivables pile up. This is a classic earnings manipulation
            signal — revenue looks great but cash isn't coming in.

        Source: Standard EY audit procedure for revenue recognition risk.
        """
        flags = []
        try:
            rev_current = income_df["Total Revenue"].iloc[0]
            rev_prior = income_df["Total Revenue"].iloc[1]
            rec_current = balance_sheet_df["Accounts Receivable"].iloc[0]
            rec_prior = balance_sheet_df["Accounts Receivable"].iloc[1]

            if rev_prior > 0 and rec_prior > 0:
                rev_growth = (rev_current - rev_prior) / rev_prior
                rec_growth = (rec_current - rec_prior) / rec_prior

                ratio = rec_growth / rev_growth if rev_growth > 0 else None

                if ratio and ratio > 2.0:
                    flags.append(
                        AnomalyFlag(
                            flag_type="REVENUE_QUALITY",
                            severity="HIGH",
                            description=(
                                f"Receivables growing {ratio:.1f}x faster than revenue. "
                                f"Revenue growth: {rev_growth:.1%}, "
                                f"Receivables growth: {rec_growth:.1%}. "
                                f"Potential revenue recognition risk."
                            ),
                            metric_value=round(ratio, 2),
                        )
                    )
                elif ratio and ratio > 1.5:
                    flags.append(
                        AnomalyFlag(
                            flag_type="REVENUE_QUALITY",
                            severity="MEDIUM",
                            description=(
                                f"Receivables growing {ratio:.1f}x faster than revenue. "
                                f"Monitor for collection issues."
                            ),
                            metric_value=round(ratio, 2),
                        )
                    )
        except (KeyError, IndexError, ZeroDivisionError):
            pass
        return flags

    def check_earnings_quality(
        self, income_df: pd.DataFrame, cash_flow_df: pd.DataFrame
    ) -> List[AnomalyFlag]:
        """
        Check if operating cash flow is significantly below net income.

        Why this matters:
            Net income can be inflated through accruals.
            Cash flow cannot be faked as easily.
            If net income >> operating cash flow consistently,
            earnings quality is poor — a classic red flag in audits.

        Source: Accruals ratio analysis, standard in EY financial audits.
        """
        flags = []
        try:
            net_income = income_df["Net Income"].iloc[0]
            operating_cf = cash_flow_df["Operating Cash Flow"].iloc[0]

            if net_income > 0:
                ratio = operating_cf / net_income

                if ratio < 0:
                    flags.append(
                        AnomalyFlag(
                            flag_type="EARNINGS_QUALITY",
                            severity="HIGH",
                            description=(
                                f"Negative operating cash flow despite positive net income. "
                                f"Net Income: {net_income / 1e9:.1f}B, "
                                f"Operating CF: {operating_cf / 1e9:.1f}B. "
                                f"Strong accruals manipulation signal."
                            ),
                            metric_value=round(ratio, 2),
                        )
                    )
                elif ratio < 0.7:
                    flags.append(
                        AnomalyFlag(
                            flag_type="EARNINGS_QUALITY",
                            severity="MEDIUM",
                            description=(
                                f"Operating cash flow is only {ratio:.0%} of net income. "
                                f"Earnings may be overstated through accruals."
                            ),
                            metric_value=round(ratio, 2),
                        )
                    )
        except (KeyError, IndexError, ZeroDivisionError):
            pass

        return flags

    def check_debt_sustainability(
        self, income_df: pd.DataFrame, balance_sheet_df: pd.DataFrame
    ) -> List[AnomalyFlag]:
        """
        Check leverage and interest coverage ratios.

        Why this matters:
            High debt relative to earnings = financial distress risk.
            Low interest coverage = company struggling to service debt.
            These are core solvency checks from EY audit procedures.

        Thresholds:
            Net Debt/EBITDA > 4x = HIGH risk
            Net Debt/EBITDA > 3x = MEDIUM risk
            Interest Coverage < 2x = HIGH risk
            Interest Coverage < 3x = MEDIUM risk
        """
        flags = []
        try:
            ebitda = income_df["EBITDA"].iloc[0]
            total_debt = balance_sheet_df["Total Debt"].iloc[0]
            cash = balance_sheet_df["Cash And Cash Equivalents"].iloc[0]
            net_debt = total_debt - cash

            if ebitda > 0:
                leverage = net_debt / ebitda
                if leverage > 4.0:
                    flags.append(
                        AnomalyFlag(
                            flag_type="LEVERAGE",
                            severity="HIGH",
                            description=(
                                f"Net Debt/EBITDA of {leverage:.1f}x exceeds 4x threshold. "
                                f"Net Debt: {net_debt / 1e9:.1f}B, "
                                f"EBITDA: {ebitda / 1e9:.1f}B. "
                                f"High financial distress risk."
                            ),
                            metric_value=round(leverage, 2),
                        )
                    )
                elif leverage > 3.0:
                    flags.append(
                        AnomalyFlag(
                            flag_type="LEVERAGE",
                            severity="MEDIUM",
                            description=(
                                f"Net Debt/EBITDA of {leverage:.1f}x approaching elevated levels. "
                                f"Monitor debt trajectory."
                            ),
                            metric_value=round(leverage, 2),
                        )
                    )
        except (KeyError, IndexError, ZeroDivisionError):
            pass

        try:
            ebit = income_df["EBIT"].iloc[0]
            interest_expense = abs(income_df["Interest Expense"].iloc[0])

            if interest_expense > 0:
                coverage = ebit / interest_expense
                if coverage < 2.0:
                    flags.append(
                        AnomalyFlag(
                            flag_type="INTEREST_COVERAGE",
                            severity="HIGH",
                            description=(
                                f"Interest coverage ratio of {coverage:.1f}x is critically low. "
                                f"Company may struggle to service debt."
                            ),
                            metric_value=round(coverage, 2),
                        )
                    )
                elif coverage < 3.0:
                    flags.append(
                        AnomalyFlag(
                            flag_type="INTEREST_COVERAGE",
                            severity="MEDIUM",
                            description=(
                                f"Interest coverage ratio of {coverage:.1f}x is below 3x. "
                                f"Monitor debt servicing capacity."
                            ),
                            metric_value=round(coverage, 2),
                        )
                    )
        except (KeyError, IndexError, ZeroDivisionError):
            pass

        return flags

    def check_margin_trends(
        self,
        income_df: pd.DataFrame,
    ) -> List[AnomalyFlag]:
        """
        Check for significant margin compression year over year.

        Why this matters:
            Sudden margin compression signals pricing pressure,
            rising costs, or competitive deterioration.
            Sustained margin decline = structural problem.

        Thresholds:
            Gross margin compression > 300bps = HIGH
            Gross margin compression > 150bps = MEDIUM
        """
        flags = []
        try:
            if len(income_df) >= 2:
                gp_current = income_df["Gross Profit"].iloc[0]
                rev_current = income_df["Total Revenue"].iloc[0]
                gp_prior = income_df["Gross Profit"].iloc[1]
                rev_prior = income_df["Total Revenue"].iloc[1]

                margin_current = gp_current / rev_current
                margin_prior = gp_prior / rev_prior
                compression = margin_prior - margin_current

                if compression > 0.03:
                    flags.append(
                        AnomalyFlag(
                            flag_type="MARGIN_COMPRESSION",
                            severity="HIGH",
                            description=(
                                f"Gross margin compressed by {compression * 100:.0f}bps YoY. "
                                f"Current: {margin_current:.1%}, "
                                f"Prior: {margin_prior:.1%}. "
                                f"Significant pricing or cost pressure."
                            ),
                            metric_value=round(compression, 2),
                        )
                    )
                elif compression > 0.015:
                    flags.append(
                        AnomalyFlag(
                            flag_type="MARGIN_COMPRESSION",
                            severity="MEDIUM",
                            description=(
                                f"Gross margin compressed by {compression * 100:.0f}bps YoY. "
                                f"Monitor for continued deterioration."
                            ),
                            metric_value=round(compression, 4),
                        )
                    )
        except (KeyError, IndexError, ZeroDivisionError):
            pass

        return flags

    def check_cash_conversion(
        self,
        income_df: pd.DataFrame,
        cash_flow_df: pd.DataFrame,
    ) -> List[AnomalyFlag]:
        """
        Check free cash flow conversion from net income.

        Why this matters:
            A healthy business converts most of its net income
            into free cash flow. Poor conversion signals heavy
            capex requirements or working capital deterioration.

        Threshold:
            FCF / Net Income < 0.5 = MEDIUM concern
            FCF negative while Net Income positive = HIGH concern
        """
        flags = []
        try:
            net_income = income_df["Net Income"].iloc[0]
            fcf = cash_flow_df["Free Cash Flow"].iloc[0]

            if net_income > 0:
                if fcf < 0:
                    flags.append(
                        AnomalyFlag(
                            flag_type="CASH_CONVERSION",
                            severity="HIGH",
                            description=(
                                f"Negative free cash flow ({fcf / 1e9:.1f}B) "
                                f"despite positive net income ({net_income / 1e9:.1f}B). "
                                f"Heavy capex or working capital drain."
                            ),
                            metric_value=round(fcf / net_income, 2),
                        )
                    )
                elif fcf / net_income < 0.5:
                    flags.append(
                        AnomalyFlag(
                            flag_type="CASH_CONVERSION",
                            severity="MEDIUM",
                            description=(
                                f"FCF conversion of {fcf / net_income:.0%} is below 50%. "
                                f"FCF: {fcf / 1e9:.1f}B, "
                                f"Net Income: {net_income / 1e9:.1f}B."
                            ),
                            metric_value=round(fcf / net_income, 2),
                        )
                    )
        except (KeyError, IndexError, ZeroDivisionError):
            pass

        return flags

    def run(
        self,
        ticker: str,
        income_df: pd.DataFrame,
        balance_sheet_df: pd.DataFrame,
        cash_flow_df: pd.DataFrame,
    ) -> dict:
        """
        Run all anomaly checks on a company's financial statements.

        Args:
            ticker: stock symbol
            income_df: from fetcher.get_income_statement()
            balance_sheet_df: from fetcher.get_balance_sheet()
            cash_flow_df: from fetcher.get_cash_flow()

        Returns:
            dict with all flags organised by severity
        """
        all_flags = []

        all_flags += self.check_revenue_quality(income_df, balance_sheet_df)
        all_flags += self.check_earnings_quality(income_df, cash_flow_df)
        all_flags += self.check_debt_sustainability(income_df, balance_sheet_df)
        all_flags += self.check_margin_trends(income_df)
        all_flags += self.check_cash_conversion(income_df, cash_flow_df)

        high = [f for f in all_flags if f.severity == "HIGH"]
        medium = [f for f in all_flags if f.severity == "MEDIUM"]
        low = [f for f in all_flags if f.severity == "LOW"]

        return {
            "ticker": ticker,
            "total_flags": len(all_flags),
            "high_count": len(high),
            "medium_count": len(medium),
            "low_count": len(low),
            "flags": [
                {
                    "type": f.flag_type,
                    "severity": f.severity,
                    "description": f.description,
                    "metric_value": f.metric_value,
                }
                for f in all_flags
            ],
            "risk_level": (
                "HIGH" if high else "MEDIUM" if medium else "LOW" if low else "CLEAN"
            ),
        }
