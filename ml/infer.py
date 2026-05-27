from __future__ import annotations

import logging
from datetime import datetime, timezone

import numpy as np
import tensorflow as tf

from ml.dataset import (
    FEATURE_COLUMNS,
    TARGET_COLUMNS,
    add_months,
    load_monthly_frame,
    load_scaler,
    model_paths,
    naive_forecast,
)
from src.config import settings
from src.database import SessionLocal
from src.models import Forecast, ModelRun

logger = logging.getLogger(__name__)


def _write_forecasts(
    *,
    generated_at: datetime,
    horizon: int,
    last_period,
    predictions: dict[str, list[float]],
    model_run_id: int | None,
    method: str,
) -> int:
    db = SessionLocal()
    try:
        count = 0
        for metric in TARGET_COLUMNS:
            for step, value in enumerate(predictions[metric], start=1):
                target_month = add_months(last_period, step)
                db.add(
                    Forecast(
                        generated_at=generated_at,
                        horizon_months=horizon,
                        target_month=target_month,
                        metric=metric,
                        point_estimate=float(value),
                        lower_bound=None,
                        upper_bound=None,
                        model_run_id=model_run_id,
                    )
                )
                count += 1
        if model_run_id is None:
            run = ModelRun(
                started_at=generated_at,
                finished_at=generated_at,
                artifact_path=None,
                metrics={"method": method},
                status="completed",
                notes=f"Forecast via {method}",
            )
            db.add(run)
        db.commit()
        return count
    finally:
        db.close()


def run_inference() -> dict:
    frame = load_monthly_frame()
    horizon = settings.forecast_horizon
    window = settings.lstm_window
    generated_at = datetime.now(timezone.utc)

    if frame.empty:
        return {"status": "skipped", "message": "No company monthly data available"}

    last_period = frame["period"].iloc[-1]
    model_path, _ = model_paths()
    scaler = load_scaler()

    if len(frame) < settings.min_training_rows or not model_path.exists() or scaler is None:
        predictions = naive_forecast(frame, horizon)
        count = _write_forecasts(
            generated_at=generated_at,
            horizon=horizon,
            last_period=last_period,
            predictions=predictions,
            model_run_id=None,
            method="naive_seasonal",
        )
        return {
            "status": "ok",
            "message": "Used naive seasonal fallback",
            "forecasts_written": count,
            "method": "naive_seasonal",
        }

    model = tf.keras.models.load_model(model_path)
    recent = frame.tail(window)[FEATURE_COLUMNS].astype(float).values
    scaled = scaler.transform(recent)
    x = np.expand_dims(scaled, axis=0)
    y_scaled = model.predict(x, verbose=0)[0]

    profit_idx = FEATURE_COLUMNS.index("profit")
    revenue_idx = FEATURE_COLUMNS.index("revenue")
    dummy = np.zeros((horizon, len(FEATURE_COLUMNS)))
    dummy[:, profit_idx] = y_scaled[:, 0]
    dummy[:, revenue_idx] = y_scaled[:, 1]
    inverse = scaler.inverse_transform(dummy)

    predictions = {
        "profit": inverse[:, profit_idx].tolist(),
        "revenue": inverse[:, revenue_idx].tolist(),
    }

    db = SessionLocal()
    try:
        latest_run = db.query(ModelRun).filter(ModelRun.status == "completed").order_by(ModelRun.id.desc()).first()
        model_run_id = latest_run.id if latest_run else None
    finally:
        db.close()

    count = _write_forecasts(
        generated_at=generated_at,
        horizon=horizon,
        last_period=last_period,
        predictions=predictions,
        model_run_id=model_run_id,
        method="lstm",
    )
    return {
        "status": "ok",
        "message": "LSTM forecast generated",
        "forecasts_written": count,
        "method": "lstm",
        "model_run_id": model_run_id,
    }
