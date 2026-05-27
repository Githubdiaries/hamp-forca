from __future__ import annotations

import logging
from datetime import datetime, timezone

import numpy as np
from sklearn.preprocessing import MinMaxScaler

from ml.dataset import (
    FEATURE_COLUMNS,
    build_sequences,
    load_monthly_frame,
    model_paths,
    naive_forecast,
    save_scaler,
    split_train_val,
)
from ml.model import build_lstm_model
from src.config import settings
from src.database import SessionLocal
from src.models import ModelRun

logger = logging.getLogger(__name__)


def run_training() -> dict:
    frame = load_monthly_frame()
    row_count = len(frame)
    window = settings.lstm_window
    horizon = settings.forecast_horizon

    if row_count < settings.min_training_rows:
        message = (
            f"Insufficient history ({row_count} rows). "
            f"Need at least {settings.min_training_rows} for LSTM training."
        )
        logger.warning(message)
        return {
            "status": "skipped",
            "message": message,
            "row_count": row_count,
            "fallback": "naive_seasonal",
        }

    x_raw, y_raw = build_sequences(frame, window, horizon)
    if len(x_raw) < 3:
        return {
            "status": "skipped",
            "message": "Not enough sequences to train",
            "sequences": len(x_raw),
        }

    scaler = MinMaxScaler()
    flat = frame[FEATURE_COLUMNS].astype(float).values
    scaler.fit(flat)
    scaled_values = scaler.transform(flat)

    scaled_frame = frame.copy()
    scaled_frame[FEATURE_COLUMNS] = scaled_values
    x, y = build_sequences(scaled_frame, window, horizon)
    x_train, y_train, x_val, y_val = split_train_val(x, y)

    model = build_lstm_model(window, len(FEATURE_COLUMNS), horizon)
    history = model.fit(
        x_train,
        y_train,
        validation_data=(x_val, y_val) if len(x_val) else None,
        epochs=settings.train_epochs,
        batch_size=min(8, len(x_train)),
        verbose=0,
    )

    model_path, _ = model_paths()
    model.save(model_path)
    save_scaler(scaler)

    val_loss = float(history.history["val_loss"][-1]) if "val_loss" in history.history else None
    train_mae = float(history.history["mae"][-1])
    metrics = {
        "train_mae": train_mae,
        "val_loss": val_loss,
        "epochs": len(history.history["loss"]),
        "sequences": len(x),
    }

    db = SessionLocal()
    try:
        run = ModelRun(
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            artifact_path=str(model_path),
            metrics=metrics,
            status="completed",
            notes="LSTM training completed",
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return {
            "status": "ok",
            "message": "Model trained successfully",
            "model_run_id": run.id,
            "metrics": metrics,
            "artifact_path": str(model_path),
        }
    finally:
        db.close()
