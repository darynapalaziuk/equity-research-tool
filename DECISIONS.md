# Architecture Decision Records

---

## ADR-001: yfinance as Data Source

**Status:** Accepted

**Context:** The project requires live financial data — income statements, balance sheets, cash flows, market prices. Professional data providers exist but are not accessible for personal projects.

**Decision:** yfinance (Yahoo Finance wrapper) selected as the primary data source. Standard choice for portfolio projects in the Python finance ecosystem.

**Consequences:** Rate limiting applies. All fetched data is cached locally for 24 hours via diskcache. For production deployment, only `src/data/fetcher.py` would need to change — all valuation logic remains data-source agnostic.

---

## ADR-002: PostgreSQL over SQLite

**Status:** Accepted

**Context:** The project stores valuation results for historical tracking. A persistent, production-grade database is required.

**Decision:** PostgreSQL 15 running in Docker. Schema managed via Alembic migrations.

**Consequences:** Docker must be running. Any schema change requires an Alembic migration file. The setup is reproducible with `docker-compose up -d`.

---

## ADR-003: Shared `calculations.py` Module

**Status:** Accepted

**Context:** CAPM, terminal growth rate, and equity risk premium calculations are required by both DCF and DDM. Duplicating them would risk inconsistency between models.

**Decision:** Shared functions extracted to `src/utils/calculations.py`. Both valuation engines import from this module.

**Consequences:** Both models always use identical inputs for shared calculations. Adding a new valuation model reuses existing financial logic without duplication.

---

## ADR-004: Market D/E over Book D/E for WACC

**Status:** Accepted

**Context:** WACC requires debt and equity weights. Two options exist: book value weights (from balance sheet) or market value weights (from market cap).

**Decision:** Market D/E (Total Debt / Market Cap) used as primary method, per Damodaran and CFA curriculum. Falls back to Book D/E when market data is unavailable, then to industry average 0.3 if book equity is negative.

**Consequences:** WACC more accurately reflects investor perspective. For asset-light companies with negative book equity (e.g. Apple due to buybacks), the calculation remains valid.

---

## ADR-005: ERP Calculated From S&P 500 Earnings Yield

**Status:** Accepted

**Context:** Equity Risk Premium is required for CAPM. A hardcoded value ignores current market conditions.

**Decision:** ERP derived from S&P 500 trailing earnings yield minus the risk-free rate. Country-specific risk premiums added from Damodaran's annual dataset (NYU Stern), cached for one year.

**Consequences:** ERP adjusts with market conditions. Fallback to Damodaran's published January 2026 estimate (4.23%) if S&P 500 data is unavailable.

---

## ADR-006: Terminal Growth Rate From Treasury Yield

**Status:** Accepted

**Context:** DCF and DDM require a long-run terminal growth rate. A hardcoded value becomes stale as interest rates change.

**Decision:** Terminal growth rate = 10Y Treasury yield / 2, floored at 1.5% and capped at 3.5%.

**Consequences:** Terminal growth rate adjusts with the interest rate environment. The floor and cap prevent unrealistic values in extreme rate environments.

---

## ADR-007: DDM Excluded for Dividend Yield Below 1%

**Status:** Accepted

**Context:** DDM produces meaningless results for companies with very small dividends relative to their stock price (e.g. Apple: 0.41% yield → DDM implies ~$15 for a $258 stock).

**Decision:** DDM excluded when dividend yield < 1%. Report distinguishes between two cases: company pays no dividends vs dividend yield too low for meaningful valuation.

**Consequences:** Blended valuation is more accurate. Users receive clear explanation of why DDM was excluded rather than a misleading price target.

---

## ADR-008: Python 3.11

**Status:** Accepted

**Context:** Python 3.14 was available at project start. Key dependencies (pandas, numpy, scipy) had not yet published pre-compiled wheels for 3.14, requiring compilation from source which failed on macOS.

**Decision:** Python 3.11 — most stable version for the scientific Python ecosystem at time of development.

**Consequences:** All dependencies install without compilation issues. Project must be updated when upgrading Python version.

---

## ADR-009: CAGR Over ARIMA for FCF Projection

**Status:** Accepted

**Context:** ARIMA was considered for FCF projection as a more 
sophisticated alternative to historical CAGR.

**Decision:** CAGR retained. yfinance provides only 5 annual FCF 
observations — insufficient for reliable ARIMA parameter estimation 
(minimum 20-30 required). With 5 points ARIMA reduces to a linear 
trend, offering no advantage over CAGR while adding model complexity 
and fragility.

**Consequences:** FCF projections use historical CAGR with scenario 
multipliers (worst 60%, base 100%, best 120%). This is conservative 
and transparent. For production use with longer data series (10+ years 
from a paid provider), ARIMA(p,1,q) would be appropriate.

---