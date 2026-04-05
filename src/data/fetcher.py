import time

import yfinance as yf
import pandas as pd
from diskcache import Cache

cache = Cache("./cache")
CACHE_TTL = 86400


class FinancialDataFetcher:

    def _get_ticker(self, ticker: str) -> yf.Ticker:
        """
        Get yfinance Ticker object with caching.
        """
        return yf.Ticker(ticker)

    def get_income_statement(self, ticker: str) -> pd.DataFrame:
        """
        Fetch annual income statements for a company.
        Returns: DataFrame with columns like revenue, ebitda, net_income etc.
        """
        cache_key = f"income_statement/{ticker}"
        if cache_key in cache:
            return cache[cache_key]

        stock = self._get_ticker(ticker)
        df = stock.financials.T
        df.index = pd.to_datetime(df.index)
        df = df.sort_index(ascending=False)

        cache.set(cache_key, df, expire=CACHE_TTL)
        return df

    def get_balance_sheet(self, ticker: str) -> pd.DataFrame:
        """
        Fetch annual balance sheets for a company.
        Returns: DataFrame with columns like totalAssets, totalDebt, cash etc.
        """
        cache_key = f"balance_{ticker}"
        if cache_key in cache:
            return cache[cache_key]
        stock = self._get_ticker(ticker)
        df = stock.balance_sheet.T
        df.index = pd.to_datetime(df.index)
        df = df.sort_index(ascending=False)

        cache.set(cache_key, df, expire=CACHE_TTL)
        return df

    def get_cash_flow(self, ticker: str, years: int = 5) -> pd.DataFrame:
        """
        Fetch annual cash flow statements for a company.
        Returns: DataFrame with columns like operationCashFlow, capitalExpenditure etc.
        """
        cache_key = f"cashflow_{ticker}"
        if cache_key in cache:
            return cache[cache_key]

        stock = self._get_ticker(ticker)
        df = stock.cashflow.T
        df.index = pd.to_datetime(df.index)
        df = df.sort_index(ascending=False)

        cache.set(cache_key, df, expire=CACHE_TTL)
        return df

    def get_current_price(self, ticker: str) -> float:
        """
        Fetch current market price.
        """
        stock = self._get_ticker(ticker)
        price = stock.info.get("currentPrice")
        if not price:
            raise ValueError(f"Could not fetch  price for {ticker}")
        return price

    def get_beta(self, ticker:str) -> float:
        """
        Fetch beta (market sensitivity) from yfinance.
        Beta > 1 means more volatile than market.
        Beta < 0 means less volatile than market.
        """
        stock = self._get_ticker(ticker)
        return stock.info.get("beta", 1.0) or 1.0

    def get_risk_free_rate(self) -> float:
        """
        Fetch current 10-year US Treasury yield as risk-free rate proxy.
        Used in CAPM and WACC calculations.
        """
        cache_key = "risk_free_rate"
        if cache_key in cache:
            return cache[cache_key]

        try:
            tnx = yf.Ticker("^TNX")
            rate = tnx.history(period="5d")["Close"].iloc[-1] / 100
            cache.set(cache_key, rate, expire=CACHE_TTL)
            return rate
        except Exception:
            return 0.0431

    def get_shares_outstanding(self, ticker: str) -> float:
        """
        Fetch number of shares outstanding.
        Used to convert enterprise value to per-share price.
        """
        stock = yf.Ticker(ticker)
        shares = stock.info.get("sharesOutstanding")
        if not shares:
            raise ValueError(f"Could not fetch shares outstanding for {ticker}")
        return shares

    def get_company_info(self, ticker: str) -> dict:
        """
        Fetch basic company infos.
        Return name, sector, industry etc.
        """
        stock = self._get_ticker(ticker)
        info = stock.info
        return {
            "name": info.get("longName", ticker),
            "sector": info.get("sector", "Unknown"),
            "country": info.get("country", "Unknown"),
            "ticker": ticker
        }
        cache.set(cache_key, result, expire=CACHE_TTL)
        return result

    def get_dividend_history(self, ticker: str) -> pd.Series:
        """
        Fetch historical dividend payments from yfinance.
        Returns a pandas Series of dividend amounts indexed by date.
        """
        cache_key = f"dividend_history_{ticker}"
        if cache_key in cache:
            return cache[cache_key]

        stock = yf.Ticker(ticker)
        result = stock.dividends
        cache.set(cache_key, result, expire=CACHE_TTL)
        return result

    def get_dividend_data(self, ticker: str) -> dict:
        """
        Fetch current dividend information.

        Returns dict with:
            annual_dividend: current annual dividend per share
            payout_ratio: % of earnings paid as dividends
            dividend_yield: annual dividend / current price
            has_dividends: True if company pays dividends
        """
        cache_key = f"dividend_data_{ticker}"
        if cache_key in cache:
            return cache[cache_key]

        stock = yf.Ticker(ticker)
        info = stock.info

        annual_dividend = info.get("dividendRate") or 0.0
        payout_ratio = info.get("payoutRatio") or 0.0
        dividend_yield = info.get("dividendYield") or 0.0

        result = {
            "annual_dividend": annual_dividend,
            "payout_ratio": payout_ratio,
            "dividend_yield": dividend_yield,
            "has_dividends": annual_dividend > 0
        }
        cache.set(cache_key, result, expire=CACHE_TTL)
        return result

    def get_multiples(self, ticker: str) -> dict:
        """
        Fetch market multiples for a single company.
        Used for both target and peer comparables analysis.
        """
        cache_key = f"multiples_{ticker}"
        if cache_key in cache:
            return cache[cache_key]

        time.sleep(1.5)  # rate limit protection
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