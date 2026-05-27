from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class CompanyMonthlyRow(BaseModel):
    period: date
    sales_volume: float = 0
    revenue: float = 0
    profit: float = 0
    currency: str = "GBP"
    notes: Optional[str] = None


class CompanyMonthlyBatch(BaseModel):
    rows: list[CompanyMonthlyRow]


class ProductRow(BaseModel):
    name: str
    category: Optional[str] = None
    active_from: Optional[date] = None
    active_to: Optional[date] = None


class ProductBatch(BaseModel):
    rows: list[ProductRow]


class JobResponse(BaseModel):
    status: str
    message: str
    details: dict = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str = "ok"
