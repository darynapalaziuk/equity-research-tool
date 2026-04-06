import argparse

from src.audit.anomaly_detector import AnomalyDetector
from src.data.database import save_valuation_result
from src.data.fetcher import FinancialDataFetcher
from src.reporting.output import _blend_valuation, print_report
from src.valuation.comparables import ComparablesValuation
from src.valuation.dcf import DCFValuation
from src.valuation.ddm import DDMValuation


def main():
    parser = argparse.ArgumentParser(description="Automated equity research tool")
    parser.add_argument(
        "--ticker", required=True, help="Stock ticker to analyze e.g. AAPL"
    )
    parser.add_argument(
        "--peers",
        nargs="+",
        required=True,
        help="Peer tickers for comparables e.g. MSFT GOOGL META",
    )
    parser.add_argument(
        "--scenario",
        default="base",
        choices=["worst", "base", "best"],
        help="DCF scenario: worst, base, or best (default: base)",
    )
    args = parser.parse_args()

    ticker = args.ticker.upper()
    peers = [p.upper() for p in args.peers]
    scenario = args.scenario

    print(f"\nAnalyzing {ticker}...")
    print(f"Peers: {', '.join(peers)}")
    print(f"Scenario: {scenario}\n")

    f = FinancialDataFetcher()

    print("Fetching financial data...")
    income = f.get_income_statement(ticker)
    balance = f.get_balance_sheet(ticker)
    cashflow = f.get_cash_flow(ticker)
    beta = f.get_beta(ticker)
    rfr = f.get_risk_free_rate()
    shares = f.get_shares_outstanding(ticker)
    price = f.get_current_price(ticker)
    info = f.get_company_info(ticker)
    dividend_data = f.get_dividend_data(ticker)
    dividend_history = f.get_dividend_history(ticker)

    print("Running valuations...")

    dcf = DCFValuation()
    dcf_result = dcf.run(
        ticker=ticker,
        income_df=income,
        cash_flow_df=cashflow,
        balance_sheet_df=balance,
        beta=beta,
        risk_free_rate=rfr,
        shares_outstanding=shares,
        country=info.get("country", "United States"),
        scenario=scenario,
    )

    comps = ComparablesValuation()
    comps_result = comps.run(ticker=ticker, peers=peers)

    ddm = DDMValuation()
    ddm_result = None
    try:
        ddm_result = ddm.run(
            ticker=ticker,
            dividend_data=dividend_data,
            dividend_history=dividend_history,
            beta=beta,
            risk_free_rate=rfr,
            country=info.get("country", "United States"),
        )
    except ValueError:
        pass

    detector = AnomalyDetector()
    anomaly_result = detector.run(
        ticker=ticker, income_df=income, balance_sheet_df=balance, cash_flow_df=cashflow
    )

    # ── Blend valuation ──
    blended_price, weights, upside, recommendation = _blend_valuation(
        current_price=price,
        dcf_result=dcf_result,
        comps_result=comps_result,
        ddm_result=ddm_result,
    )

    # ── Save to database ──
    try:
        save_valuation_result(
            ticker=ticker,
            company_name=info.get("name", ticker),
            sector=info.get("sector", "Unknown"),
            dcf_value=dcf_result["dcf_price_target"],
            ddm_value=ddm_result["ddm_price_target"] if ddm_result else None,
            comparables_value=comps_result.get("comps_price_target"),
            blended_value=blended_price,
            recommendation=recommendation,
        )
    except Exception as e:
        print(f"⚠️  Could not save to database: {e}")

    # ── Print report ──
    print_report(
        ticker=ticker,
        company_info=info,
        current_price=price,
        dcf_result=dcf_result,
        comps_result=comps_result,
        anomaly_result=anomaly_result,
        ddm_result=ddm_result,
        scenario=scenario,
    )


if __name__ == "__main__":
    main()
