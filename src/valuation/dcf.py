import pandas as pd

from src.utils.calculations import (
    calculate_cost_of_equity,
    get_equity_risk_premium,
    get_terminal_growth_rate,
)


class DCFValuation:
    """
    Discounted Cash Flow valuation engine.

    Follows a 6-step methodology:
    Step 1: Project future free cash flows
    Step 2: Calculate free cash flows from financials
    Step 3: Calculate WACC as discount factor
    Step 4: Calculate terminal value
    Step 5: Aggregate all present values to get enterprise value
    Step 6: Scenario analysis (worst, base, best)
    """

    def calculate_cost_of_debt(
        self,
        income_df: pd.DataFrame,
        balance_sheet_df: pd.DataFrame,
        risk_free_rate: float,
    ) -> tuple:
        """
        Cost of debt = Interest Expense / Total Debt
        Calculated from real financial statements.
        Falls back to Rf + 1.5% credit spread if data missing.
        Returns: (value, source)
        """
        try:
            interest_expense = abs(income_df["Interest Expense"].dropna().iloc[0])
            total_debt = balance_sheet_df["Total Debt"].dropna().iloc[0]
            if total_debt > 0 and interest_expense > 0:
                cod = round(float(interest_expense / total_debt), 4)
                return cod, "calculated from financials"
        except (KeyError, IndexError):
            pass

        fallback = round(risk_free_rate + 0.015, 4)
        return fallback, "fallback: RF + 1.5% credit spread"

    def calculate_tax_rate(self, income_df: pd.DataFrame) -> tuple:
        """
        Effective tax rate from income statement.
        First tries Tax Rate For Calcs.
        Falls back to Tax Provision / Pretax Income.
        Falls back to US statutory rate 21%.
        Returns: (value, source)
        """
        try:
            tax_rate = float(income_df["Tax Rate For Calcs"].dropna().iloc[0])
            if 0 < tax_rate <= 1:
                return round(tax_rate, 4), "calculated from financials"
        except (KeyError, IndexError):
            pass

        try:
            tax = float(income_df["Tax Provision"].dropna().iloc[0])
            pretax = float(income_df["Pretax Income"].dropna().iloc[0])
            if pretax > 0:
                return round(tax / pretax, 4), "calculated from financials"
        except (KeyError, IndexError):
            pass

        return 0.21, "fallback: US statutory rate 21%"

    def calculate_debt_to_equity(
        self,
        balance_sheet_df: pd.DataFrame,
        shares_outstanding: float = None,
        current_price: float = None,
    ) -> tuple:
        """
        D/E ratio for WACC calculation.

        Uses Market D/E (Total Debt / Market Cap) when possible.
        Market D/E is theoretically correct for WACC per Damodaran.
        Falls back to Book D/E if market data unavailable.
        Falls back to industry average 0.3 if both unavailable.
        """
        try:
            debt = float(balance_sheet_df["Total Debt"].dropna().iloc[0])

            # Prefer market D/E
            if shares_outstanding and current_price:
                market_cap = shares_outstanding * current_price
                if market_cap > 0:
                    market_de = round(debt / market_cap, 4)
                    return market_de, "calculated from market cap (Market D/E)"

            # Fall back to book D/E
            equity = float(balance_sheet_df["Stockholders Equity"].dropna().iloc[0])
            if equity > 0:
                return round(debt / equity, 4), "calculated from financials (Book D/E)"

        except (KeyError, IndexError):
            pass

        return 0.3, "fallback: industry average D/E"

    def calculate_wacc(
        self,
        cost_of_equity: float,
        cost_of_debt: float,
        tax_rate: float,
        debt_to_equity: float,
    ) -> float:
        """
        Step 3: WACC = (E/V) x Re + (D/V) x Rd x (1 - Tc)
        Higher WACC = higher risk = lower valuation.
        """
        equity_weight = 1 / (1 + debt_to_equity)
        debt_weight = debt_to_equity / (1 + debt_to_equity)

        wacc = equity_weight * cost_of_equity + debt_weight * cost_of_debt * (
            1 - tax_rate
        )
        return round(wacc, 4)

    def get_historical_fcf(
        self,
        cash_flow_df: pd.DataFrame,
    ) -> list:
        """
        Step 2: Extract historical free cash flows.
        Returns only positive FCF years, most recent first.
        """
        fcf = cash_flow_df["Free Cash Flow"].dropna().tolist()
        return [f for f in fcf if f > 0]

    def project_fcf(self, historical_fcf: list, scenario: str = "base") -> tuple:
        """
        Step 1: Project FCF for next 5 years.

        Growth rate from historical FCF CAGR.
        Three scenarios:
            worst: 60% of base growth
            base:  historical CAGR with gradual decline
            best:  120% of base growth

        Returns: (projected_fcf_list, growth_rate_used)
        """
        if len(historical_fcf) >= 2:
            cagr = (historical_fcf[0] / historical_fcf[-1]) ** (
                1 / (len(historical_fcf) - 1)
            ) - 1
            cagr = min(max(cagr, 0.02), 0.25)
        else:
            cagr = 0.05

        scenario_multipliers = {"worst": 0.6, "base": 1.0, "best": 1.2}
        adjusted_cagr = cagr * scenario_multipliers.get(scenario, 1.0)

        growth_schedule = [
            adjusted_cagr,
            adjusted_cagr * 0.85,
            adjusted_cagr * 0.70,
            adjusted_cagr * 0.55,
            adjusted_cagr * 0.40,
        ]

        base = historical_fcf[0]
        projected = []
        for rate in growth_schedule:
            base = base * (1 + rate)
            projected.append(round(base, 0))

        return projected, round(adjusted_cagr, 4)

    def calculate_terminal_value(
        self, final_year_fcf: float, wacc: float, terminal_growth_rate: float
    ) -> float:
        """
        Step 4: Terminal Value = FCF x (1+g) / (WACC - g)
        Represents all value beyond year 5.
        WACC must exceed terminal growth rate.
        """
        if wacc <= terminal_growth_rate:
            raise ValueError(
                f"WACC ({wacc:.2%}) must exceed "
                f"terminal growth rate ({terminal_growth_rate:.2%})."
            )

        tv = final_year_fcf * (1 + terminal_growth_rate) / (wacc - terminal_growth_rate)
        return round(tv, 4)

    def calculate_present_values(
        self, projected_fcf: list, terminal_value: float, wacc: float
    ) -> dict:
        """
        Step 5: Discount all cash flows to present value.
        Discount factor = 1 / (1 + WACC)^n
        """
        pv_fcfs = []
        for i, fcf in enumerate(projected_fcf):
            discount_factor = 1 / (1 + wacc) ** (i + 1)
            pv_fcfs.append(round(fcf * discount_factor, 0))

        pv_terminal = round(terminal_value / (1 + wacc) ** len(projected_fcf), 0)

        enterprise_value = sum(pv_fcfs) + pv_terminal

        return {
            "pv_fcfs": pv_fcfs,
            "pv_terminal": pv_terminal,
            "enterprise_value": round(enterprise_value, 0),
        }

    def enterprise_to_equity_per_share(
        self,
        enterprise_value: float,
        balance_sheet_df: pd.DataFrame,
        shares_outstanding: float,
    ) -> tuple:
        """
        Equity Value = Enterprise Value - Net Debt
        Price = Equity Value / Shares Outstanding
        Returns: (price, net_debt)
        """
        total_debt = float(balance_sheet_df["Total Debt"].dropna().iloc[0] or 0)
        cash = float(
            balance_sheet_df["Cash And Cash Equivalents"].dropna().iloc[0] or 0
        )
        net_debt = total_debt - cash
        equity_value = enterprise_value - net_debt
        return round(equity_value / shares_outstanding, 2), net_debt

    def run(
        self,
        ticker: str,
        income_df: pd.DataFrame,
        cash_flow_df: pd.DataFrame,
        balance_sheet_df: pd.DataFrame,
        beta: float,
        risk_free_rate: float,
        shares_outstanding: float,
        current_price: float,
        country: str = "United States",
        scenario: str = "base",
    ) -> dict:
        """
        Run complete DCF valuation using 6-step methodology.

        Args:
            ticker: stock symbol e.g. 'AAPL'
            income_df: from fetcher.get_income_statement()
            cash_flow_df: from fetcher.get_cash_flow()
            balance_sheet_df: from fetcher.get_balance_sheet()
            beta: from fetcher.get_beta()
            risk_free_rate: from fetcher.get_risk_free_rate()
            shares_outstanding: from fetcher.get_shares_outstanding()
            country: from fetcher.get_company_info()['country']
            scenario: 'worst', 'base', or 'best'
            current_price: from fetcher.get_current_price()
        """

        # ── Shared calculations from calculations.py ──
        erp, erp_source = get_equity_risk_premium(risk_free_rate, country)
        tgr, tgr_source = get_terminal_growth_rate(risk_free_rate)
        cost_of_equity = calculate_cost_of_equity(beta, risk_free_rate, erp)

        # ── DCF specific WACC components ──
        cost_of_debt, cod_source = self.calculate_cost_of_debt(
            income_df, balance_sheet_df, risk_free_rate
        )
        tax_rate, tax_source = self.calculate_tax_rate(income_df)
        debt_to_equity, dte_source = self.calculate_debt_to_equity(
            balance_sheet_df,
            shares_outstanding=shares_outstanding,
            current_price=current_price,
        )

        # ── Step 3: WACC ──
        wacc = self.calculate_wacc(
            cost_of_equity, cost_of_debt, tax_rate, debt_to_equity
        )

        # ── Step 2: Historical FCF ──
        historical_fcf = self.get_historical_fcf(cash_flow_df)

        # ── Step 1: Project FCF ──
        projected_fcf, growth_rate = self.project_fcf(historical_fcf, scenario)

        # ── Step 4: Terminal Value ──
        terminal_value = self.calculate_terminal_value(projected_fcf[-1], wacc, tgr)

        # ── Step 5: Present Values ──
        pv_results = self.calculate_present_values(projected_fcf, terminal_value, wacc)

        # ── Per share price ──
        price, net_debt = self.enterprise_to_equity_per_share(
            pv_results["enterprise_value"], balance_sheet_df, shares_outstanding
        )

        return {
            "ticker": ticker,
            "scenario": scenario,
            "dcf_price_target": price,
            "wacc": wacc,
            "cost_of_equity": cost_of_equity,
            "cost_of_debt": cost_of_debt,
            "tax_rate": tax_rate,
            "debt_to_equity": debt_to_equity,
            "equity_risk_premium": erp,
            "terminal_growth_rate": tgr,
            "historical_fcf": historical_fcf,
            "projected_fcf": projected_fcf,
            "fcf_growth_rate": growth_rate,
            "terminal_value": terminal_value,
            "pv_fcfs": pv_results["pv_fcfs"],
            "pv_terminal": pv_results["pv_terminal"],
            "enterprise_value": pv_results["enterprise_value"],
            "net_debt": net_debt,
            "inputs": {
                "equity_risk_premium": erp_source,
                "terminal_growth_rate": tgr_source,
                "cost_of_debt": cod_source,
                "tax_rate": tax_source,
                "debt_to_equity": dte_source,
            },
        }

    def run_with_custom_wacc(
        self,
        ticker: str,
        income_df: pd.DataFrame,
        cash_flow_df: pd.DataFrame,
        balance_sheet_df: pd.DataFrame,
        beta: float,
        risk_free_rate: float,
        shares_outstanding: float,
        country: str,
        scenario: str,
        custom_wacc: float,
        custom_tgr: float,
    ) -> float:
        """
        Run DCF with custom WACC and terminal growth rate.
        Used for sensitivity analysis only.
        Returns price target as float.
        """
        historical_fcf = self.get_historical_fcf(cash_flow_df)
        projected_fcf, _ = self.project_fcf(historical_fcf, scenario)
        terminal_value = self.calculate_terminal_value(
            projected_fcf[-1], custom_wacc, custom_tgr
        )
        pv_results = self.calculate_present_values(
            projected_fcf, terminal_value, custom_wacc
        )
        price, _ = self.enterprise_to_equity_per_share(
            pv_results["enterprise_value"], balance_sheet_df, shares_outstanding
        )
        return round(float(price), 2)
