from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class CompanyMonthly(Base):
    __tablename__ = "company_monthly"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    sales_volume: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    revenue: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    profit: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="GBP")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(128))
    active_from: Mapped[date | None] = mapped_column(Date)
    active_to: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MarketDocument(Base):
    __tablename__ = "market_documents"
    __table_args__ = (UniqueConstraint("source_url", "scraped_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    markdown: Mapped[str | None] = mapped_column(Text)
    query_tag: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ok")
    firecrawl_job_meta: Mapped[dict | None] = mapped_column(JSONB, default=dict)


class MarketFeaturesMonthly(Base):
    __tablename__ = "market_features_monthly"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    doc_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_keyword_score: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, default=0)
    gift_hits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hamper_hits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    luxury_hits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discount_hits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ModelRun(Base):
    __tablename__ = "model_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    artifact_path: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    notes: Mapped[str | None] = mapped_column(Text)

    forecasts: Mapped[list["Forecast"]] = relationship(back_populates="model_run")


class Forecast(Base):
    __tablename__ = "forecasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    horizon_months: Mapped[int] = mapped_column(Integer, nullable=False)
    target_month: Mapped[date] = mapped_column(Date, nullable=False)
    metric: Mapped[str] = mapped_column(String(32), nullable=False)
    point_estimate: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    lower_bound: Mapped[float | None] = mapped_column(Numeric(14, 2))
    upper_bound: Mapped[float | None] = mapped_column(Numeric(14, 2))
    model_run_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("model_runs.id"))

    model_run: Mapped["ModelRun | None"] = relationship(back_populates="forecasts")
