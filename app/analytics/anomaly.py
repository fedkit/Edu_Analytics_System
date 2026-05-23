"""Simple anomaly detection using z-score on time series."""

from __future__ import annotations

import numpy as np
import pandas as pd


def detect_anomalies(series: pd.Series, z_threshold: float = 2.5) -> pd.Series:
    """Return boolean mask where True = anomaly (z-score exceeds threshold)."""
    if series.empty or series.std() == 0:
        return pd.Series([False] * len(series), index=series.index)
    z = (series - series.mean()) / series.std()
    return z.abs() > z_threshold


def add_anomaly_column(df: pd.DataFrame, col: str, z_threshold: float = 2.5) -> pd.DataFrame:
    df = df.copy()
    df["is_anomaly"] = detect_anomalies(df[col], z_threshold)
    return df


def rolling_zscore(series: pd.Series, window: int = 7) -> pd.Series:
    """Rolling z-score for detecting local anomalies."""
    roll_mean = series.rolling(window, min_periods=3).mean()
    roll_std  = series.rolling(window, min_periods=3).std()
    return (series - roll_mean) / roll_std.replace(0, np.nan)
