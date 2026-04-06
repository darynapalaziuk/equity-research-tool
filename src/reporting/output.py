from datetime import date

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def print_report(
    ticker: str,
    company_info: dict,
    current_price: float,
    dcf_result: dict,
    comps_result: dict,
    anomaly_result: dict,
    ddm_result: dict = None,
    scenario: str = "base",
    sensitivity_df=None,
) -> None:
    """
    Print a complete equity research report to the terminal.

    Args:
        ticker: stock symbol
        company_info: from fetcher.get_company_info()
        current_price: from fetcher.get_current_price()
        dcf_result: from DCFValuation.run()
        comps_result: from ComparablesValuation.run()
        anomaly_result: from AnomalyDetector.run()
        ddm_result: from DDMValuation.run() — optional
        scenario: worst / base / best
    """

    blended, weights, upside, recommendation = _blend_valuation(
        current_price, dcf_result, comps_result, ddm_result
    )

    console.print()
    console.print(
        Panel(
            f"[bold cyan]EQUITY RESEARCH REPORT — "
            f"{company_info.get('name', ticker).upper()} ({ticker})[/bold cyan]\n"
            f"[dim]Generated: {date.today()}  |  Scenario: {scenario.upper()}[/dim]",
            box=box.DOUBLE,
            style="cyan",
        )
    )

    console.print()
    console.print("[bold]COMPANY[/bold]")
    console.print(f"  Name:      {company_info.get('name', ticker)}")
    console.print(f"  Sector:    {company_info.get('sector', 'Unknown')}")
    console.print(f"  Country:   {company_info.get('country', 'Unknown')}")

    console.print()
    console.print("[bold]VALUATION SUMMARY[/bold]")
    console.print(f"  Current Price:      [bold]${current_price:,.2f}[/bold]")
    console.print(
        f"  DCF Target:         "
        f"${dcf_result['dcf_price_target']:,.2f}   "
        f"(weight: {weights.get('DCF', 0):.0%})"
    )
    if ddm_result:
        console.print(
            f"  DDM Target:         "
            f"${ddm_result['ddm_price_target']:,.2f}   "
            f"(weight: {weights.get('DDM', 0):.0%})"
        )
    else:
        console.print(
            "  DDM Target:         "
            "[dim]N/A — company does not pay meaningful dividends[/dim]"
        )
    if comps_result.get("comps_price_target"):
        console.print(
            f"  Comparables Target: "
            f"${comps_result['comps_price_target']:,.2f}   "
            f"(weight: {weights.get('Comps', 0):.0%})"
        )
    else:
        console.print(
            "  Comparables Target: "
            "[dim]N/A — peer data unavailable (rate limited)[/dim]"
        )
    console.print(f"  {'─' * 45}")
    console.print(f"  Blended Target:     [bold]${blended:,.2f}[/bold]")

    upside_color = "green" if upside > 0 else "red"
    console.print(
        f"  Upside/Downside:    "
        f"[{upside_color}][bold]{upside:+.1%}[/bold][/{upside_color}]"
    )
    console.print(f"  {'─' * 45}")

    rec_color = {"BUY": "green", "HOLD": "yellow", "SELL": "red"}.get(
        recommendation, "white"
    )

    console.print(
        f"  Recommendation:     "
        f"[{rec_color}][bold]{recommendation}[/bold][/{rec_color}]"
    )

    console.print()
    console.print("[bold]WACC BREAKDOWN[/bold]")
    console.print(f"  Cost of Equity:   {dcf_result['cost_of_equity']:.2%}")
    console.print(f"  Cost of Debt:     {dcf_result['cost_of_debt']:.2%}")
    console.print(f"  Tax Rate:         {dcf_result['tax_rate']:.2%}")
    console.print(f"  Debt/Equity:      {dcf_result['debt_to_equity']:.2f}x")
    console.print(f"  [bold]WACC:             {dcf_result['wacc']:.2%}[/bold]")
    console.print(f"  ERP:              {dcf_result['equity_risk_premium']:.2%}")
    console.print(f"  Terminal Growth:  {dcf_result['terminal_growth_rate']:.2%}")

    console.print()
    console.print("[bold]CASH FLOW PROJECTION[/bold]")
    hist_fcf = dcf_result.get("historical_fcf", [])
    proj_fcf = dcf_result.get("projected_fcf", [])

    if hist_fcf:
        hist_str = "  ".join([f"${x/1e9:.0f}B" for x in hist_fcf[:3]])
        console.print(f"  Historical FCF:   {hist_str}")

    if proj_fcf:
        for i, fcf in enumerate(proj_fcf):
            console.print(f"  Projected Y{i+1}:    ${fcf/1e9:.1f}B")

    console.print(
        f"  Terminal Value:   " f"${dcf_result.get('terminal_value', 0)/1e12:.2f}T"
    )

    console.print()
    console.print("[bold]PEER COMPARABLES[/bold]")

    if not comps_result.get("peers"):
        console.print(
            "  [dim]Peer data unavailable — rate limited. Run again to retry.[/dim]"
        )
    else:
        table = Table(box=box.SIMPLE)
        table.add_column("Ticker", style="cyan")
        table.add_column("Name")
        table.add_column("EV/EBITDA", justify="right")
        table.add_column("P/E", justify="right")
        table.add_column("P/S", justify="right")
        table.add_column("P/B", justify="right")

        for peer_ticker, peer_data in comps_result.get("peers", {}).items():
            table.add_row(
                peer_ticker,
                str(peer_data.get("name", ""))[:25],
                f"{peer_data.get('EV/EBITDA', 'N/A')}",
                f"{peer_data.get('P/E', 'N/A')}",
                f"{peer_data.get('P/S', 'N/A')}",
                f"{peer_data.get('P/B', 'N/A')}",
            )

        medians = comps_result.get("peer_medians", {})
        table.add_row(
            "[bold]Median[/bold]",
            "",
            f"[bold]{medians.get('EV/EBITDA', 'N/A')}[/bold]",
            f"[bold]{medians.get('P/E', 'N/A')}[/bold]",
            f"[bold]{medians.get('P/S', 'N/A')}[/bold]",
            f"[bold]{medians.get('P/B', 'N/A')}[/bold]",
        )

        target_multiples = comps_result.get("target_multiples", {})
        table.add_row(
            f"[cyan]{ticker}[/cyan]",
            company_info.get("name", "")[:25],
            f"{target_multiples.get('EV/EBITDA', 'N/A')}",
            f"{target_multiples.get('P/E', 'N/A')}",
            f"{target_multiples.get('P/S', 'N/A')}",
            f"{target_multiples.get('P/B', 'N/A')}",
        )

        console.print(table)

    console.print()
    console.print("[bold]ANOMALY FLAGS[/bold]")

    flags = anomaly_result.get("flags", [])
    if not flags:
        console.print(
            "  [green]✓ No significant anomalies detected. "
            "Financial statements appear clean.[/green]"
        )
    else:
        for flag in flags:
            color = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "blue"}.get(
                flag["severity"], "white"
            )
            console.print(
                f"  [{color}][{flag['severity']}] " f"{flag['type']}[/{color}]"
            )
            console.print(f"    {flag['description']}")

    console.print()
    console.print("[bold]DATA SOURCES[/bold]")
    for key, source in dcf_result.get("inputs", {}).items():
        console.print(f"  {key}: [dim]{source}[/dim]")

    # ── Sensitivity Analysis ──
    if sensitivity_df is not None:
        console.print()
        console.print("[bold]SENSITIVITY ANALYSIS — DCF Price Target[/bold]")
        console.print("[dim]  Rows: WACC  |  Columns: Terminal Growth Rate[/dim]")

        sens_table = Table(box=box.SIMPLE)
        sens_table.add_column("WACC \\ TGR", style="cyan")
        for col in sensitivity_df.columns:
            sens_table.add_column(col, justify="right")

        for idx, row in sensitivity_df.iterrows():
            values = []
            for val in row:
                if val is None:
                    values.append("[dim]N/A[/dim]")
                else:
                    values.append(f"${val:,.0f}")
            sens_table.add_row(str(idx), *values)

        console.print(sens_table)

    console.print()
    console.print(
        Panel(
            "[dim]This report is generated automatically from public financial data. "
            "Not financial advice. Always verify with primary sources.[/dim]",
            box=box.SIMPLE,
            style="dim",
        )
    )
    console.print()


def _blend_valuation(
    current_price: float, dcf_result: dict, comps_result: dict, ddm_result: dict = None
) -> tuple:
    dcf_price = dcf_result["dcf_price_target"]
    comps_price = comps_result.get("comps_price_target")

    if comps_price and ddm_result:
        ddm_price = ddm_result["ddm_price_target"]
        blended = dcf_price * 0.40 + comps_price * 0.40 + ddm_price * 0.20
        weights = {"DCF": 0.40, "Comps": 0.40, "DDM": 0.20}
    elif comps_price:
        blended = dcf_price * 0.50 + comps_price * 0.50
        weights = {"DCF": 0.50, "Comps": 0.50}
    elif ddm_result:
        ddm_price = ddm_result["ddm_price_target"]
        blended = dcf_price * 0.70 + ddm_price * 0.30
        weights = {"DCF": 0.70, "DDM": 0.30}
    else:
        blended = dcf_price
        weights = {"DCF": 1.0}

    blended = round(blended, 2)
    upside = (blended - current_price) / current_price

    if upside > 0.10:
        recommendation = "BUY"
    elif upside < -0.10:
        recommendation = "SELL"
    else:
        recommendation = "HOLD"

    return blended, weights, upside, recommendation
