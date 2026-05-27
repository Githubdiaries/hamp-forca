import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import CompanyMonthly, Product
from src.schemas import CompanyMonthlyBatch, CompanyMonthlyRow, JobResponse, ProductBatch

router = APIRouter(prefix="/ingest", tags=["ingest"])


def parse_period(value: str):
    for fmt in ("%Y-%m-%d", "%Y-%m", "%m/%Y", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(value.strip(), fmt)
            return parsed.date().replace(day=1)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {value}")


def upsert_company_rows(db: Session, rows: list[CompanyMonthlyRow]) -> int:
    count = 0
    for row in rows:
        period = row.period.replace(day=1)
        stmt = insert(CompanyMonthly).values(
            period=period,
            sales_volume=row.sales_volume,
            revenue=row.revenue,
            profit=row.profit,
            currency=row.currency,
            notes=row.notes,
            created_at=datetime.now(timezone.utc),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["period"],
            set_={
                "sales_volume": row.sales_volume,
                "revenue": row.revenue,
                "profit": row.profit,
                "currency": row.currency,
                "notes": row.notes,
            },
        )
        db.execute(stmt)
        count += 1
    db.commit()
    return count


@router.post("/company-monthly", response_model=JobResponse)
def ingest_company_monthly_json(payload: CompanyMonthlyBatch, db: Session = Depends(get_db)):
    count = upsert_company_rows(db, payload.rows)
    return JobResponse(status="ok", message=f"Upserted {count} monthly rows", details={"count": count})


@router.post("/company-monthly/csv", response_model=JobResponse)
async def ingest_company_monthly_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows: list[CompanyMonthlyRow] = []
    for raw in reader:
        try:
            rows.append(
                CompanyMonthlyRow(
                    period=parse_period(raw.get("period", "")),
                    sales_volume=float(raw.get("sales_volume", 0) or 0),
                    revenue=float(raw.get("revenue", 0) or 0),
                    profit=float(raw.get("profit", 0) or 0),
                    currency=(raw.get("currency") or "GBP").strip(),
                    notes=raw.get("notes"),
                )
            )
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid row: {raw} ({exc})") from exc
    if not rows:
        raise HTTPException(status_code=400, detail="CSV contains no data rows")
    count = upsert_company_rows(db, rows)
    return JobResponse(status="ok", message=f"Upserted {count} monthly rows from CSV", details={"count": count})


@router.post("/products", response_model=JobResponse)
def ingest_products(payload: ProductBatch, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    count = 0
    for row in payload.rows:
        db.add(
            Product(
                name=row.name,
                category=row.category,
                active_from=row.active_from,
                active_to=row.active_to,
                created_at=now,
            )
        )
        count += 1
    db.commit()
    return JobResponse(status="ok", message=f"Inserted {count} products", details={"count": count})
