from __future__ import annotations

from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from sqlalchemy.orm import Session

from src.config import settings
from src.database import SessionLocal
from src.models import CompanyMonthly, MarketFeaturesMonthly

FEATURE_COLUMNS = [
    "sales_volume",
    "revenue",
    "profit",
    "doc_count",
    "avg_keyword_score",
    "gift_hits",
    "hamper_hits",
    "luxury_hits",
    "discount_hits",
]
TARGET_COLUMNS = ["profit", "revenue"]


def load_monthly_frame(db: Session | None = None) -> pd.DataFrame:
    own_session = db is None
    db = db or SessionLocal()
    try:
        company_rows = db.query(CompanyMonthly).order_by(CompanyMonthly.period.asc()).all()
        market_rows = db.query(MarketFeaturesMonthly).order_by(MarketFeaturesMonthly.period.asc()).all()

        company_df = pd.DataFrame(
            [
                {
                    "period": row.period,
                    "sales_volume": float(row.sales_volume),
                    "revenue": float(row.revenue),
                    "profit": float(row.profit),
                }
                for row in company_rows
            ]
        )
        market_df = pd.DataFrame(
            [
                {
                    "period": row.period,
                    "doc_count": row.doc_count,
                    "avg_keyword_score": float(row.avg_keyword_score),
                    "gift_hits": row.gift_hits,
                    "hamper_hits": row.hamper_hits,
                    "luxury_hits": row.luxury_hits,
                    "discount_hits": row.discount_hits,
                }
                for row in market_rows
            ]
        )

        if company_df.empty:
            return pd.DataFrame(columns=["period", *FEATURE_COLUMNS])

        if market_df.empty:
            market_df = pd.DataFrame({"period": company_df["period"]})
            for col in FEATURE_COLUMNS[3:]:
                market_df[col] = 0.0

        merged = pd.merge(company_df, market_df, on="period", how="left")
        merged = merged.sort_values("period").reset_index(drop=True)
        merged[FEATURE_COLUMNS[3:]] = merged[FEATURE_COLUMNS[3:]].fillna(0)
        return merged
    finally:
        if own_session:
            db.close()


def build_sequences(frame: pd.DataFrame, window: int, horizon: int) -> tuple[np.ndarray, np.ndarray]:
    values = frame[FEATURE_COLUMNS].astype(float).values
    x_list: list[np.ndarray] = []
    y_list: list[np.ndarray] = []
    profit_idx = FEATURE_COLUMNS.index("profit")
    revenue_idx = FEATURE_COLUMNS.index("revenue")

    for idx in range(window, len(values) - horizon + 1):
        x_list.append(values[idx - window : idx])
        future = values[idx : idx + horizon]
        y_list.append(np.column_stack([future[:, profit_idx], future[:, revenue_idx]]))

    if not x_list:
        return np.empty((0, window, len(FEATURE_COLUMNS))), np.empty((0, horizon, 2))
    return np.array(x_list), np.array(y_list)


def split_train_val(x: np.ndarray, y: np.ndarray, val_months: int = 6):
    if len(x) <= val_months:
        split = max(1, len(x) // 5)
    else:
        split = len(x) - val_months
    return x[:split], y[:split], x[split:], y[split:]


def model_paths() -> tuple[Path, Path]:
    base = Path(settings.model_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base / "current.keras", base / "scaler.joblib"


def save_scaler(scaler: MinMaxScaler) -> Path:
    _, scaler_path = model_paths()
    joblib.dump(scaler, scaler_path)
    return scaler_path


def load_scaler() -> MinMaxScaler | None:
    _, scaler_path = model_paths()
    if not scaler_path.exists():
        return None
    return joblib.load(scaler_path)


def add_months(start: date, months: int) -> date:
    year = start.year + (start.month - 1 + months) // 12
    month = (start.month - 1 + months) % 12 + 1
    return date(year, month, 1)


def naive_forecast(frame: pd.DataFrame, horizon: int) -> dict[str, list[float]]:
    if frame.empty:
        return {"profit": [0.0] * horizon, "revenue": [0.0] * horizon}

    profits = frame["profit"].astype(float).values
    revenues = frame["revenue"].astype(float).values
    window = min(12, len(frame))

    profit_forecast = []
    revenue_forecast = []
    for step in range(1, horizon + 1):
        seasonal_idx = max(0, len(profits) - window + ((step - 1) % window))
        profit_forecast.append(float(profits[seasonal_idx]))
        revenue_forecast.append(float(revenues[seasonal_idx]))
    return {"profit": profit_forecast, "revenue": revenue_forecast}
