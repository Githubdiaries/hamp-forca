from datetime import date

import pandas as pd
import pytest

from ml.dataset import (
    FEATURE_COLUMNS,
    add_months,
    build_sequences,
    naive_forecast,
    split_train_val,
)


@pytest.mark.unit
class TestDatasetHelpers:
    def test_add_months_crosses_year_boundary(self):
        assert add_months(date(2024, 11, 1), 3) == date(2025, 2, 1)

    def test_build_sequences_shape(self):
        rows = 24
        window = 12
        horizon = 6
        frame = pd.DataFrame(
            {
                "period": pd.date_range("2023-01-01", periods=rows, freq="MS"),
                **{col: range(rows) for col in FEATURE_COLUMNS},
            }
        )
        x, y = build_sequences(frame, window, horizon)
        assert x.shape == (7, window, len(FEATURE_COLUMNS))
        assert y.shape == (7, horizon, 2)

    def test_build_sequences_empty_when_insufficient_rows(self):
        frame = pd.DataFrame({col: [1.0] for col in FEATURE_COLUMNS})
        frame["period"] = pd.Timestamp("2024-01-01")
        x, y = build_sequences(frame, window=12, horizon=6)
        assert x.shape[0] == 0
        assert y.shape[0] == 0

    def test_split_train_val_reserves_tail(self):
        import numpy as np

        x = np.arange(20).reshape(10, 2)
        y = np.arange(10)
        x_train, y_train, x_val, y_val = split_train_val(x, y, val_months=3)
        assert len(x_train) == 7
        assert len(x_val) == 3

    def test_naive_forecast_uses_seasonal_pattern(self):
        frame = pd.DataFrame(
            {
                "profit": [100.0, 200.0, 300.0],
                "revenue": [1000.0, 2000.0, 3000.0],
            }
        )
        result = naive_forecast(frame, horizon=3)
        assert result["profit"] == [100.0, 200.0, 300.0]
        assert result["revenue"] == [1000.0, 2000.0, 3000.0]

    def test_naive_forecast_empty_frame_returns_zeros(self):
        result = naive_forecast(pd.DataFrame(), horizon=4)
        assert result["profit"] == [0.0, 0.0, 0.0, 0.0]
        assert result["revenue"] == [0.0, 0.0, 0.0, 0.0]
