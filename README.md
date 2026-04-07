![Python](https://img.shields.io/badge/python-3.11-blue)
![Tests](https://img.shields.io/badge/tests-56%20passing-green)
![Pylint](https://img.shields.io/badge/pylint-9.31%2F10-green)
![Status](https://img.shields.io/badge/status-in%20progress-orange)
Architecture and financial methodology decisions are documented in [DECISIONS.md](DECISIONS.md).

```markdown
# Automated Equity Research Tool

> ⚠️ **Project in Progress** — Core valuation engine is complete and functional. 
> Additional features (forward estimates, econometric FCF modeling, 
> sensitivity refinements) are actively being developed.

An automated equity research tool that produces professional-grade 
valuation reports from a single command. Built as a portfolio project 
to demonstrate quantitative finance and software engineering skills.

```bash
python analyze.py --ticker AAPL --peers MSFT GOOGL META --scenario base
```

---

## What It Does

Given a stock ticker and a list of peers, the tool:

1. Fetches live financial data from Yahoo Finance
2. Runs three valuation models (DCF, DDM, Comparables)
3. Detects financial anomalies using audit-style checks
4. Produces a blended price target with BUY/HOLD/SELL recommendation
5. Saves every analysis to a PostgreSQL database for historical tracking
6. Prints a formatted equity research report in the terminal

---

## Sample Output

```
EQUITY RESEARCH REPORT — APPLE INC. (AAPL) | 2026-04-07 | BASE

Current Price: $258.86  →  Blended Target: $139.61  →  SELL (-46.1%)

DCF:   $101.77  |  Comps: $177.45  |  DDM: N/A (yield too low)
WACC:  8.44%    |  ERP:  4.23%     |  Terminal Growth: 2.17%

[HIGH] REVENUE_QUALITY — Receivables growing 3x faster than revenue
```

---

## Valuation Models

### DCF — Discounted Cash Flow
- 6-step EY-style methodology
- WACC calculated from real financials (market-weighted D/E per Damodaran)
- Three scenarios: worst (60%), base (100%), best (120% of historical CAGR)
- Country-specific equity risk premium from Damodaran's annual dataset
- Terminal growth rate derived from 10Y Treasury yield

### DDM — Dividend Discount Model
- Two-stage model with Gordon Growth terminal value
- Automatically excluded for companies with dividend yield < 1%
- Clear messaging: distinguishes between no dividends vs low yield

### Comparables — Peer Multiples
- EV/EBITDA, P/E, P/S, P/B multiples
- Peer median (not mean) to reduce outlier impact
- Weighted blend: EV/EBITDA 40%, P/E 35%, P/S 15%, P/B 10%

---

## Anomaly Detection

Five audit-style checks inspired by EY Technology Risk practice:

| Check | What It Detects |
|---|---|
| Revenue Quality | Receivables growing faster than revenue |
| Earnings Quality | Operating cash flow vs net income divergence |
| Debt Sustainability | Net Debt/EBITDA and interest coverage ratios |
| Margin Trends | Gross margin compression year over year |
| Cash Conversion | Free cash flow vs net income conversion |

---

## Sensitivity Analysis

Every report includes a 5×5 WACC/terminal growth rate sensitivity table 
showing how the DCF price target changes across different assumptions.

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.11 |
| Database | PostgreSQL 15 (Docker) |
| ORM & Migrations | SQLAlchemy + Alembic |
| Data Source | yfinance (Yahoo Finance) |
| Caching | diskcache (24-hour TTL) |
| CLI Output | rich |
| Code Quality | black, isort, pylint (9.31/10) |
| Tests | pytest (56 tests passing) |

---

## Project Structure

```
equity-research-tool/
├── analyze.py                    ← CLI entry point
├── src/
│   ├── data/
│   │   ├── fetcher.py            ← yfinance data layer (cached)
│   │   ├── models.py             ← SQLAlchemy database models
│   │   └── database.py           ← valuation result persistence
│   ├── valuation/
│   │   ├── dcf.py                ← DCF engine
│   │   ├── ddm.py                ← DDM engine
│   │   ├── comparables.py        ← Peer multiples engine
│   │   └── sensitivity.py        ← Sensitivity analysis
│   ├── audit/
│   │   └── anomaly_detector.py   ← 5 EY-style audit checks
│   ├── reporting/
│   │   └── output.py             ← rich CLI report formatter
│   └── utils/
│       ├── calculations.py       ← Shared: ERP, CAPM, terminal growth
│       └── config.py             ← Environment config
├── tests/                        ← 56 pytest tests
├── migrations/                   ← Alembic migrations
└── docker-compose.yml
```

---

## Installation

**Prerequisites:** Python 3.11, Docker Desktop

```bash
# Clone the repository
git clone https://github.com/darynapalaziuk/equity-research-tool.git
cd equity-research-tool

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env and set DB_PASSWORD

# Start PostgreSQL
docker-compose up -d

# Run database migrations
alembic upgrade head
```

---

## Usage

```bash
# Basic analysis
python analyze.py --ticker AAPL --peers MSFT GOOGL META

# With scenario
python analyze.py --ticker AAPL --peers MSFT GOOGL META --scenario worst

# European company example
python analyze.py --ticker ASML --peers AMAT LRCX KLAC

# Dividend-paying company (DDM applies)
python analyze.py --ticker JNJ --peers PFE MRK ABBV
```

---

## Running Tests

```bash
pytest tests/ -v
```

```
56 passed in 70.01s
```

---

## Data Source Note

This tool uses Yahoo Finance via yfinance for market data. Yahoo Finance 
applies rate limits — if you encounter errors on first run, wait 5 minutes 
and try again. All data is cached locally after the first successful run, 
so subsequent runs are instant.

For production deployment, replacing yfinance with a paid API 
(Financial Modeling Prep, Alpha Vantage, or Polygon.io) would eliminate 
rate limiting. Only `src/data/fetcher.py` would need to change — 
all valuation logic remains identical.

---

## What's In Progress

- [ ] Forward estimates integration (analyst EPS/revenue consensus)
- [ ] Econometric FCF modeling (ARIMA/GARCH instead of historical CAGR)
- [ ] Total Shareholder Yield DDM (dividends + buybacks)
- [ ] Sensitivity analysis refinements
- [ ] DECISIONS.md — architectural decision documentation
- [ ] maybe more:)

---

## Author

Daryna Palaziuk  
Paris, France  
[GitHub](https://github.com/darynapalaziuk) | [LinkedIn](https://www.linkedin.com/in/daryna-palaziuk/)
```