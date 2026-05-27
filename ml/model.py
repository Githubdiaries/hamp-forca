from __future__ import annotations

import tensorflow as tf
from tensorflow.keras import Sequential
from tensorflow.keras.layers import Dense, Dropout, LSTM


def build_lstm_model(window: int, n_features: int, horizon: int) -> tf.keras.Model:
    model = Sequential(
        [
            LSTM(64, input_shape=(window, n_features), return_sequences=True),
            Dropout(0.2),
            LSTM(32),
            Dropout(0.2),
            Dense(horizon * 2),
        ]
    )
    model.add(tf.keras.layers.Reshape((horizon, 2)))
    model.compile(optimizer="adam", loss="mse", metrics=["mae"])
    return model
