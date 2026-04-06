import time
import random
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

    def _get_info(self, ticker: str) -> dict:
        """
        Fetch all stock info using requests-cache session.
        requests-cache is a known workaround for yfinance rate limiting.
        """
        cache_key = f"info_{ticker}"
        if cache_key in cache:
            return cache[cache_key]

        try:
            import requests_cache
            session = requests_cache.CachedSession(
                "yfinance_cache",
                expire_after=86400
            )
            stock = yf.Ticker(ticker, session=session)
            info = stock.info

            if info and len(info) > 5:
                cache.set(cache_key, info, expire=CACHE_TTL)
                return info

        except Exception as e:
            print(f"⚠️  Failed to fetch info for {ticker}: {e}")
            return {}

        return {}

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

        if not df.empty:
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

        if not df.empty:
            cache.set(cache_key, df, expire=CACHE_TTL)
        return df

    def get_cash_flow(self, ticker: str) -> pd.DataFrame:
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

        if not df.empty:
            cache.set(cache_key, df, expire=CACHE_TTL)
        return df

    def get_current_price(self, ticker: str) -> float:
        cache_key = f"price_{ticker}"
        if cache_key in cache:
            return cache[cache_key]
        info = self._get_info(ticker)
        price = info.get("currentPrice")
        if not price:
            raise ValueError(f"Price unavailable for {ticker}")
        cache.set(cache_key, price, expire=CACHE_TTL)
        return price

    def get_beta(self, ticker: str) -> float:
        cache_key = f"beta_{ticker}"
        if cache_key in cache:
            return cache[cache_key]
        info = self._get_info(ticker)
        beta = info.get("beta", 1.0) or 1.0
        cache.set(cache_key, beta, expire=CACHE_TTL)
        return beta

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
        cache_key = f"shares_{ticker}"
        if cache_key in cache:
            return cache[cache_key]
        info = self._get_info(ticker)
        shares = info.get("sharesOutstanding")
        if not shares:
            raise ValueError(f"Shares outstanding unavailable for {ticker}")
        cache.set(cache_key, shares, expire=CACHE_TTL)
        return shares

    def get_company_info(self, ticker: str) -> dict:
        cache_key = f"company_info_{ticker}"
        if cache_key in cache:
            return cache[cache_key]
        info = self._get_info(ticker)
        result = {
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
        cache_key = f"dividend_data_{ticker}"
        if cache_key in cache:
            return cache[cache_key]
        info = self._get_info(ticker)
        result = {
            "annual_dividend": info.get("dividendRate") or 0.0,
            "payout_ratio": info.get("payoutRatio") or 0.0,
            "dividend_yield": info.get("dividendYield") or 0.0,
            "has_dividends": (info.get("dividendRate") or 0.0) > 0
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