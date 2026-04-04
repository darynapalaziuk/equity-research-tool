import yfinance as yf
import pandas as pd
from diskcache import Cache

cache = Cache("./cache")
CACHE_TTL_YEAR = 365 * 24* 3600

def get_country_risk_premiums() -> dict:
    """
    Fetch country risk premiums from Damodaran's annual Excel file.
    Updated every January at NYU Stern.
    Cached for 1 year since data only changes annually.

    Returns: dict of {country_name: crp_value}
    """
    cache_key = "damodaran_crp"
    if cache_key in cache:
        return cache[cache_key]

    try:
        url = "https://www.stern.nyu.edu/~adamodar/pc/datasets/ctryprem.xlsx"
        df = pd.read_excel(url, sheet_name=0)

        crp_dict = {}
        for _, row in df.iterrows():
            try:
                country = str(row.iloc[0]).strip()
                for val in reversed(row.tolist()):
                    try:
                        crp = float(val)
                        if 0 <= crp < 50:
                            crp_dict[country] = round(crp / 100, 4)
                            break
                    except (TypeError, ValueError):
                        continue
            except Exception:
                continue

        if crp_dict:
            cache.set(cache_key, crp_dict, expire=CACHE_TTL_YEAR)
            return crp_dict

    except Exception:
        pass

    return {
        "United States": 0.0000,
        "Germany": 0.0047,
        "France": 0.0047,
        "Netherlands": 0.0047,
        "United Kingdom": 0.0047,
        "Switzerland": 0.0000,
        "Sweden": 0.0023,
        "Japan": 0.0047,
        "South Korea": 0.0071,
        "China": 0.0094,
        "Taiwan": 0.0071,
        "India": 0.0141,
        "Canada": 0.0000,
        "Australia": 0.0000,
        "Singapore": 0.0000,
        "Ukraine": 0.0908,
    }


def get_base_erp(risk_free_rate: float) -> float:
    """
    Calculate base US ERP from S&P 500 earnings yield.
    ERP = Earnings Yield - Risk Free Rate
    """
    try:
        sp500 = yf.Ticker("^GSPC")
        pe = sp500.info.get("trailingPE")
        if pe and pe > 0:
            earnings_yield = 1 / pe
            erp = earnings_yield - risk_free_rate
            return max(min(erp, 0.12), 0.02)
    except Exception:
        pass
    return 0.0423 # Damodaran January 2026 fallback


def get_equity_risk_premium(
        risk_free_rate: float,
        country: str = "United States"
) -> tuple:
    """
        Calculate total ERP for a specific country.
    Total ERP = Base ERP (US) + Country Risk Premium

    If country not found in dataset, falls back to USA (0.00% CRP)
    and warns the user explicitly.

    Returns: (value, source)
    """
    base_erp = get_base_erp(risk_free_rate)
    crp_data = get_country_risk_premiums()

    if country not in crp_data:
        print(
            f"⚠️  Warning: '{country}' not found in Damodaran country risk "
            f"dataset. Falling back to United States (CRP = 0.00%). "
            f"This may UNDERESTIMATE risk for non-US companies. "
            f"Verify country name at: "
            f"stern.nyu.edu/~adamodar/New_Home_Page/datafile/ctryprem.html"
        )
        country = "United States"

    crp = crp_data[country]
    total_erp = round(base_erp + crp, 4)
    source = (
        f"Base ERP ({base_erp:.2%}) + "
        f"{country} CRP ({crp:.2%}) — Damodaran 2026"
    )
    return total_erp, source

def calculate_cost_of_equity(
        beta: float,
        risk_free_rate: float,
        equity_risk_premium: float
) -> float:
    """
        CAPM: Re = Rf + Beta x ERP

    Used in both DCF and DDM valuation.

    Args:
        beta: company market sensitivity from fetcher
        risk_free_rate: 10Y Treasury yield from fetcher
        equity_risk_premium: from get_equity_risk_premium()
    """
    return round(risk_free_rate + beta * equity_risk_premium, 4)

def get_terminal_growth_rate(risk_free_rate: float) -> tuple:
   """
   Derive terminal growth rate from 10Y Treasury yield.

    Logic:
        No company can grow faster than the economy forever.
        10Y Treasury yield / 2 is a conservative proxy
        for long-run nominal GDP growth.

    Floored at 1.5%, capped at 3.5%.
    Used in both DCF and DDM valuation.

    Returns: (value, source)
    """
   tgr = risk_free_rate / 2
   tgr = max(tgr, 0.015)
   tgr = min(tgr, 0.035)
   return round(tgr, 4), "derived from 10Y Treasury yield / 2"