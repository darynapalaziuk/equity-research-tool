from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, DateTime
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

class Company(Base):
    __tablename__ = 'companies'

    id = Column(Integer, primary_key=True)
    ticker = Column(String, unique=True, nullable=False)
    name = Column(String)
    sector = Column(String)
    created_at = Column(DateTime, default=datetime.now)

    income_statements = relationship("IncomeStatement", back_populates="company")
    balance_sheets = relationship("BalanceSheet", back_populates="company")
    cash_flows = relationship("CashFlow", back_populates="company")
    valuations = relationship("ValuationResult", back_populates="company")
    anomaly_flags = relationship("AnomalyFlag", back_populates="company")


class IncomeStatement(Base):
    __tablename__ = 'income_statements'

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    date = Column(Date, nullable=False)
    revenue = Column(Float)
    gross_profit = Column(Float)
    ebitda = Column(Float)
    net_income = Column(Float)
    eps = Column(Float)
    operating_income = Column(Float)

    company = relationship("Company", back_populates="income_statements")


class BalanceSheet(Base):
    __tablename__ = 'balance_sheets'

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    date = Column(Date, nullable=False)
    total_assets = Column(Float)
    total_debt = Column(Float)
    cash = Column(Float)
    total_equity = Column(Float)
    receivables = Column(Float)
    inventory = Column(Float)

    company = relationship("Company", back_populates="balance_sheets")


class CashFlow(Base):
    __tablename__ = 'cash_flows'

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    date = Column(Date, nullable=False)
    operating_cash_flow = Column(Float)
    capex = Column(Float)
    free_cash_flow = Column(Float)
    dividends_paid = Column(Float)

    company = relationship("Company", back_populates="cash_flows")


class ValuationResult(Base):
    __tablename__ = 'valuation_results'

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    date = Column(Date, nullable=False)
    dcf_value = Column(Float)
    ddm_value = Column(Float)
    comparables_value = Column(Float)
    blended_value = Column(Float)
    recommendation = Column(String)
    created_at = Column(DateTime, default=datetime.now)

    company = relationship("Company", back_populates="valuations")


class AnomalyFlag(Base):
    __tablename__ = 'anomaly_flags'

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    detected_at = Column(Date, nullable=False)
    flag_type = Column(String)
    severity = Column(String)
    description = Column(String)
    metric_value = Column(Float)

    company = relationship("Company", back_populates="anomaly_flags")