import yfinance as yf
import pandas as pd
from diskcache import Cache
from statsmodels.graphics.tukeyplot import results

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
        cache_key = f"income-statement/{ticker}"
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

        if not df.empty:
            cache.set(cache_key, df, expire=CACHE_TTL)
        return df

    def get_current_price(self, ticker: str) -> float:
        """
        Fetch current market price.
        """
        cache_key = f"price_{ticker}"
        if cache_key in cache:
            return cache[cache_key]

        stock = self._get_ticker(ticker)
        price = stock.info.get("currentPrice")
        if not price:
            raise ValueError(f"Could not fetch  price for {ticker}")
        cache.set(cache_key, price, expire=CACHE_TTL)
        return price

    def get_beta(self, ticker:str) -> float:
        """
        Fetch beta (market sensitivity) from yfinance.
        Beta > 1 means more volatile than market.
        Beta < 0 means less volatile than market.
        """
        cache_key = f"beta_{ticker}"
        if cache_key in cache:
            return cache[cache_key]

        stock = yf.Ticker(ticker)
        beta = stock.info.get("beta", 1.0) or 1.0
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

        tnx = yf.Ticker("^TNX")
        rate = tnx.history(period="1d")["Close"].iloc[-1]/100
        cache.set(cache_key, rate, expire=CACHE_TTL)
        return rate

    def get_shares_outstanding(self, ticker: str) -> float:
        """
        Fetch number of shares outstanding.
        Used to convert enterprise value to per-share price.
        """
        cache_key = f"shares_{ticker}"
        if cache_key in cache:
            return cache[cache_key]

        stock = yf.Ticker(ticker)
        shares = stock.info.get("sharesOutstanding")
        if not shares:
            raise ValueError(f"Could not fetch shares outstanding for {ticker}")
        cache.set(cache_key, shares, expire=CACHE_TTL)
        return shares

    def get_company_info(self, ticker: str) -> dict:
        """
        Fetch basic company infos.
        Return name, sector, industry etc.
        """
        cache_key = f"company_info_{ticker}"
        if cache_key in cache:
            return cache[cache_key]

        stock = self._get_ticker(ticker)
        info = stock.info
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