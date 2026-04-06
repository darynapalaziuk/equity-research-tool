import pandas as pd

from src.utils.calculations import (calculate_cost_of_equity,
                                    get_equity_risk_premium,
                                    get_terminal_growth_rate)


class DDMValuation:
    """
    Dividend Discount Model valuation engine.

    Values a company based on present value of future dividends.
    Uses two-stage model:
        Stage 1: Project dividends for 5 years
        Stage 2: Terminal value using Gordon Growth Model

    Key difference from DCF:
        DCF discounts free cash flows using WACC.
        DDM discounts dividends using cost of equity only.
        Dividends are payments to equity holders, not debt holders.

    Only applicable to companies that consistently pay dividends.
    """

    def _calculate_dividend_growth_rate(
        self, dividend_history: pd.Series, years: int = 5
    ) -> tuple:
        """
        Calculate historical dividend growth rate (CAGR).
        Private method — only used internally by DDM.

        Args:
            dividend_history: from fetcher.get_dividend_history()
            years: number of years to calculate CAGR over

        Returns: (growth_rate, source)
        """
        try:
            if dividend_history is None or len(dividend_history) < 2:
                raise ValueError("Insufficient dividend history")

            history = dividend_history.copy()
            if history.index.tz is not None:
                history.index = history.index.tz_convert(None)

            annual = dividend_history.resample("YE").sum()
            annual = annual[annual > 0]

            if len(annual) >= 2:
                first = float(annual.iloc[-min(years, len(annual))])
                last = float(annual.iloc[-1])
                n = min(years, len(annual)) - 1

                if first > 0 and n > 0:
                    cagr = (last / first) ** (1 / n) - 1
                    cagr = max(min(cagr, 0.20), 0.0)
                    return (round(cagr, 4), f"historical dividend CAGR ({n} years)")
        except Exception:
            pass

        return 0.05, "fallback: 5% default dividend growth rate"

    def check_ddm_applicability(self, ticker: str, dividend_data: dict) -> None:
        if not dividend_data["has_dividends"]:
            raise ValueError(
                f"DDM not applicable for {ticker}. "
                f"Company does not pay dividends. "
                f"Use DCF valuation instead."
            )

        if dividend_data["dividend_yield"] < 0.01:
            raise ValueError(
                f"DDM not applicable for {ticker}. "
                f"Dividend yield of {dividend_data['dividend_yield']:.2%} "
                f"is too low for meaningful DDM valuation. "
                f"DDM works best for mature dividend-focused companies "
                f"such as Johnson & Johnson or Coca-Cola."
            )

        if dividend_data["payout_ratio"] > 0.95:
            print(
                f"⚠️  Warning: {ticker} has very high payout ratio "
                f"({dividend_data['payout_ratio']:.0%}). "
                f"Dividend may not be sustainable."
            )

    def project_dividends(
        self, current_dividend: float, growth_rate: float, years: int = 5
    ) -> list:
        """
        Stage 1: Project dividends for next 5 years.

        Uses constant growth rate — appropriate for mature
        dividend-paying companies whose dividends grow
        at a stable rate year over year.
        """
        dividends = []
        div = current_dividend
        for _ in range(years):
            div = div * (1 + growth_rate)
            dividends.append(round(div, 4))
        return dividends

    def calculate_terminal_value(
        self, final_dividend: float, cost_of_equity: float, terminal_growth_rate: float
    ) -> float:
        """
        Stage 2: Gordon Growth Model terminal value.

        TV = D x (1 + g) / (re - g)

        Where:
            D  = final projected dividend
            g  = terminal growth rate (from calculations.py)
            re = cost of equity (not WACC — dividends are equity only)

        Cost of equity must exceed terminal growth rate.
        """
        if cost_of_equity <= terminal_growth_rate:
            raise ValueError(
                f"Cost of equity ({cost_of_equity:.2%}) must exceed "
                f"terminal growth rate ({terminal_growth_rate:.2%}). "
                f"Check your inputs."
            )

        tv = (
            final_dividend
            * (1 + terminal_growth_rate)
            / (cost_of_equity - terminal_growth_rate)
        )
        return round(tv, 4)

    def calculate_present_values(
        self, projected_dividends: list, terminal_value: float, cost_of_equity: float
    ) -> dict:
        """
        Discount all dividends and terminal value to present value.

        Discount factor = 1 / (1 + re)^n

        Uses cost of equity as discount rate — not WACC.
        This is the key technical difference from DCF.
        """
        pv_dividends = []
        for i, div in enumerate(projected_dividends):
            discounted_factor = 1 / (1 + cost_of_equity) ** (i + 1)
            pv_dividends.append(round(div * discounted_factor, 4))

        pv_terminal = round(
            terminal_value / (1 + cost_of_equity) ** len(projected_dividends), 4
        )

        equity_value = sum(pv_dividends) + pv_terminal

        return {
            "pv_dividends": pv_dividends,
            "pv_terminal": pv_terminal,
            "equity_value": round(equity_value, 4),
        }

    def run(
        self,
        ticker: str,
        dividend_data: dict,
        dividend_history: pd.Series,
        beta: float,
        risk_free_rate: float,
        country: str = "United States",
    ) -> dict:
        """
        Run complete DDM valuation.

        Args:
            ticker: stock symbol e.g. 'JNJ'
            dividend_data: from fetcher.get_dividend_data()
            dividend_history: from fetcher.get_dividend_history()
            beta: from fetcher.get_beta()
            risk_free_rate: from fetcher.get_risk_free_rate()
            country: from fetcher.get_company_info()['country']

        Raises ValueError if company does not pay dividends.
        """

        self.check_ddm_applicability(ticker, dividend_data)

        erp, erp_source = get_equity_risk_premium(risk_free_rate, country)
        tgr, tgr_source = get_terminal_growth_rate(risk_free_rate)
        cost_of_equity = calculate_cost_of_equity(beta, risk_free_rate, erp)

        div_growth, div_growth_source = self._calculate_dividend_growth_rate(
            dividend_history
        )

        projected_dividends = self.project_dividends(
            dividend_data["annual_dividend"], div_growth
        )

        terminal_value = self.calculate_terminal_value(
            projected_dividends[-1], cost_of_equity, tgr
        )

        pv_results = self.calculate_present_values(
            projected_dividends, terminal_value, cost_of_equity
        )

        return {
            "ticker": ticker,
            "ddm_price_target": pv_results["equity_value"],
            "current_annual_dividend": dividend_data["annual_dividend"],
            "dividend_yield": dividend_data["dividend_yield"],
            "payout_ratio": dividend_data["payout_ratio"],
            "dividend_growth_rate": div_growth,
            "projected_dividends": projected_dividends,
            "cost_of_equity": cost_of_equity,
            "equity_risk_premium": erp,
            "terminal_growth_rate": tgr,
            "terminal_value": terminal_value,
            "pv_dividends": pv_results["pv_dividends"],
            "pv_terminal": pv_results["pv_terminal"],
            "inputs": {
                "equity_risk_premium": erp_source,
                "terminal_growth_rate": tgr_source,
                "dividend_growth_rate": div_growth_source,
            },
        }
