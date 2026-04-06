import time

import pandas as pd
import yfinance as yf

from diskcache import Cache
cache = Cache("./cache")
CACHE_TTL = 86400


class ComparablesValuation:
    """
    Comparables (Multiples) valuation engine.

    Values a company by comparing it to similar peers
    using market multiples:
        - EV/EBITDA  — enterprise value relative to earnings
        - P/E        — price relative to earnings per share
        - P/S        — price relative to revenue per share
        - P/B        — price relative to book value per share

    Logic:
        If Company A and Company B are in the same industry
        with similar growth and risk profiles, they should
        trade at similar multiples. If Company A trades at
        a discount to peers, it may be undervalued.

    Key difference from DCF and DDM:
        Relative valuation — depends on market pricing peers correctly.
        DCF and DDM are absolute — depend on fundamental assumptions.
        Together they give a fuller picture.
    """

    def get_peer_multiples(self, peers: list) -> pd.DataFrame:
        """
        Fetch current market multiples for peer companies.

        Multiples fetched:
            EV/EBITDA  — most widely used in M&A and equity research
            P/E        — price to trailing earnings
            P/S        — price to sales (useful for unprofitable companies)
            P/B        — price to book value

        Args:
            peers: list of ticker symbols e.g. ['MSFT', 'GOOGL', 'META']

        Returns:
            DataFrame with one row per peer and columns for each multiple
        """
        data = []
        for ticker in peers:
            try:
                cache_key = f"multiples_{ticker}"
                if cache_key in cache:
                    data.append(cache[cache_key])
                    continue

                time.sleep(2)

                stock = yf.Ticker(ticker)
                info = stock.info

                ev_ebitda = info.get("enterpriseToEbitda")
                pe = info.get("trailingPE")
                ps = info.get("priceToSalesTrailing12Months")
                pb = info.get("priceToBook")
                name = info.get("shortName", ticker)

                if any([ev_ebitda, pe, ps, pb]):
                    row = {
                        "ticker": ticker,
                        "name": name,
                        "EV/EBITDA": ev_ebitda,
                        "P/E": pe,
                        "P/S": ps,
                        "P/B": pb
                    }
                    cache.set(cache_key, row, expire=CACHE_TTL)
                    data.append(row)
                else:
                    print(f"⚠️  Warning: No multiples data available for {ticker}")

            except Exception as e:
                print(f"⚠️  Warning: Could not fetch data for {ticker}: {e}")

        if not data:
            print("⚠️  No peer data available due to rate limiting. Comparables skipped.")
            return pd.DataFrame(columns=["name", "EV/EBITDA", "P/E", "P/S", "P/B"])

        return pd.DataFrame(data).set_index("ticker")

    def get_target_multiples(self, ticker: str) -> dict:
        """
        Fetch current multiples for the target company.
        Used to compare against peer median.
        """
        cache_key = f"multiples_{ticker}"
        if cache_key in cache:
            return cache[cache_key]

        time.sleep(1.5)
        stock = yf.Ticker(ticker)
        info = stock.info

        result = {
            "ticker": ticker,
            "name": info.get("shortName", ticker),
            "current_price": info.get("currentPrice"),
            "shares_outstanding": info.get("sharesOutstanding"),
            "ebitda": info.get("ebitda"),
            "trailing_eps": info.get("trailingEps"),
            "revenue_per_share": info.get("revenuePerShare"),
            "book_value_per_share": info.get("bookValue"),
            "total_debt": info.get("totalDebt") or 0,
            "total_cash": info.get("totalCash") or 0,
            "EV/EBITDA": info.get("enterpriseToEbitda"),
            "P/E": info.get("trailingPE"),
            "P/S": info.get("priceToSalesTrailing12Months"),
            "P/B": info.get("priceToBook")
        }

        if any([result["EV/EBITDA"], result["P/E"],
                result["P/S"], result["P/B"]]):
            cache.set(cache_key, result, expire=CACHE_TTL)

        return result

    def calculate_peer_medians(
            self,
            peer_multiples: pd.DataFrame,
    ) -> dict:
        """
        Calculate median multiples across peers.

        Uses median instead of mean to reduce impact of outliers.
        One company with an extreme multiple would skew mean badly.

        Returns dict with median for each multiple.
        """
        medians = {}
        for col in ["EV/EBITDA", "P/E", "P/S", "P/B"]:
            values = peer_multiples[col].dropna()
            if len(values) > 0:
                medians[col] = round(float(values.median()), 2)
            else:
                medians[col] = None
        return medians

    def calculate_implied_prices(
            self,
            target: dict,
            peer_medians: dict
    ) -> dict:
        """
        Calculate implied share price for each multiple.

        Logic:
            If peers trade at median EV/EBITDA of 15x
            and target has EBITDA of $10B
            then implied Enterprise Value = $150B
            subtract net debt → equity value → divide by shares

        Returns dict with implied price per multiple.
        """
        implied = {}

        if peer_medians.get("P/E") and target.get("trailing_eps"):
            try:
                implied["P/E"] = round(
                    peer_medians["P/E"] * target["trailing_eps"], 2
                )
            except (TypeError, ZeroDivisionError):
                implied["P/E"] = None

        if peer_medians.get("P/S") and target.get("revenue_per_share"):
            try:
                implied["P/S"] = round(
                    peer_medians["P/S"] * target["revenue_per_share"], 2
                )
            except (TypeError, ZeroDivisionError):
                implied["P/S"] = None

        if peer_medians.get("P/B") and target.get("book_value_per_share"):
            try:
                implied["P/B"] = round(
                    peer_medians["P/B"] * target["book_value_per_share"], 2
                )
            except (TypeError, ZeroDivisionError):
                implied["P/B"] = None

        if peer_medians.get("EV/EBITDA") and target.get("ebitda"):
            try:
                total_debt = target.get("total_debt") or 0
                cash = target.get("total_cash") or 0
                net_debt = total_debt - cash
                shares = target.get("shares_outstanding") or 1

                implied_ev = peer_medians["EV/EBITDA"] * target["ebitda"]
                implied_equity = implied_ev - net_debt
                implied["EV/EBITDA"] = round(implied_equity / shares, 2)
            except (TypeError, ZeroDivisionError):
                implied["EV/EBITDA"] = None

        return implied

    def calculate_blended_price(
            self,
            implied_prices: dict
    ) -> tuple:
        """
        Calculate blended price from all available multiples.

        Weights:
            EV/EBITDA  40% — most reliable for mature companies
            P/E        35% — most widely watched by investors
            P/S        15% — useful supplement
            P/B        10% — least reliable for asset-light companies

        Returns: (blended_price, weights_used)
        """
        weight = {
            "EV/EBITDA": 0.40,
            "P/E": 0.35,
            "P/S": 0.15,
            "P/B": 0.10,
        }

        available = {
            k: v for k, v in implied_prices.items()
            if v is not None and v > 0
        }

        if not available:
            raise ValueError("No valid implied prices to blend.")

        total_weight = sum(weight[k] for k in available)
        blended = sum(
            available[k] * weight[k] / total_weight
            for k in available
        )

        weight_used = {
            k: round(weight[k] / total_weight, 2)
            for k in available
        }

        return round(blended, 2), weight_used

    def run(
        self,
        ticker: str,
        peers: list
    ) -> dict:
        """
        Run complete comparables valuation.

        Args:
            ticker: target company e.g. 'AAPL'
            peers: list of comparable companies e.g. ['MSFT', 'GOOGL']

        Returns:
            Complete comparables result with peer table,
            implied prices per multiple, and blended target.
        """
        if not peers:
            raise ValueError(
                "Peers list cannot be empty. "
                "Provide at least 2-3 comparable companies."
            )

        if len(peers) < 2:
            print(
                "⚠️  Warning: Only 1 peer provided. "
                "Comparables are more reliable with 3+ peers."
            )

        peer_multiples = self.get_peer_multiples(peers)

        if peer_multiples.empty:
            return {
                "ticker": ticker,
                "comps_price_target": None,
                "target_multiples": {},
                "current_price": None,
                "peers": {},
                "peer_medians": {},
                "implied_prices": {},
                "weight_used": {},
                "premium_discount": {}
            }

        target = self.get_target_multiples(ticker)

        peer_medians = self.calculate_peer_medians(peer_multiples)

        implied_prices = self.calculate_implied_prices(target, peer_medians)

        blended_price, weight_used = self.calculate_blended_price(
            implied_prices
        )

        return {
            "ticker": ticker,
            "comps_price_target": blended_price,

            "target_multiples": {
                k: target.get(k)
                for k in ["EV/EBITDA", "P/E", "P/S", "P/B"]
            },
            "current_price": target.get("current_price"),

            "peers": peer_multiples.to_dict(orient="index"),
            "peer_medians": peer_medians,

            "implied_prices": implied_prices,
            "weight_used": weight_used,

            "premium_discount": {
                multiple: round(
                    (target.get(multiple) or 0) /
                    (peer_medians.get(multiple) or 1) - 1, 4
                )
                for multiple in ["EV/EBITDA", "P/E", "P/S", "P/B"]
                if peer_medians.get(multiple)
            }
        }