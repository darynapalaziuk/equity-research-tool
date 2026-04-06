from datetime import date
from sqlalchemy import create_engine, text
from src.utils.config import DB_URL


def get_engine():
    """Create SQLAlchemy engine from environment config."""
    return create_engine(DB_URL)


def save_valuation_result(
    ticker: str,
    company_name: str,
    sector: str,
    dcf_value: float,
    ddm_value: float,
    comparables_value: float,
    blended_value: float,
    recommendation: str
) -> None:
    engine = get_engine()

    with engine.connect() as conn:
        result = conn.execute(
            text("""
                INSERT INTO companies (ticker, name, sector, created_at)
                VALUES (:ticker, :name, :sector, NOW())
                ON CONFLICT (ticker) DO UPDATE
                SET name = EXCLUDED.name,
                    sector = EXCLUDED.sector
                RETURNING id
            """),
            {
                "ticker": ticker,
                "name": company_name,
                "sector": sector
            }
        )
        company_id = result.fetchone()[0]

        conn.execute(
            text("""
                INSERT INTO valuation_results (
                    company_id, date, dcf_value, ddm_value,
                    comparables_value, blended_value,
                    recommendation, created_at
                )
                VALUES (
                    :company_id, :date, :dcf_value, :ddm_value,
                    :comparables_value, :blended_value,
                    :recommendation, NOW()
                )
            """),
            {
                "company_id": company_id,
                "date": date.today(),
                "dcf_value": float(dcf_value) if dcf_value is not None else None,
                "ddm_value": float(ddm_value) if ddm_value is not None else None,
                "comparables_value": float(comparables_value) if comparables_value is not None else None,
                "blended_value": float(blended_value) if blended_value is not None else None,
                "recommendation": recommendation
            }
        )

        conn.commit()
        print(f"✅ Valuation saved to database for {ticker}")


def get_valuation_history(ticker: str) -> list:
    """
    Fetch historical valuations for a company from the database.

    Returns list of dicts with date, blended_value, recommendation.
    """
    engine = get_engine()

    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT
                    vr.date,
                    vr.dcf_value,
                    vr.ddm_value,
                    vr.comparables_value,
                    vr.blended_value,
                    vr.recommendation,
                    vr.created_at
                FROM valuation_results vr
                JOIN companies c ON c.id = vr.company_id
                WHERE c.ticker = :ticker
                ORDER BY vr.date DESC
                LIMIT 10
            """),
            {"ticker": ticker}
        )

        rows = result.fetchall()
        return [
            {
                "date": str(row[0]),
                "dcf_value": row[1],
                "ddm_value": row[2],
                "comparables_value": row[3],
                "blended_value": row[4],
                "recommendation": row[5],
                "created_at": str(row[6])
            }
            for row in rows
        ]