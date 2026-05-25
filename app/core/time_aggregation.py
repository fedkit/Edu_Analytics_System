"""Временна́я агрегация: ресемплинг, скользящие средние, производные."""
from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd

Granularity = Literal["daily", "weekly", "monthly"]

FREQ: dict[str, str] = {"daily": "D", "weekly": "W-MON", "monthly": "MS"}
GRANULARITY_LABELS: dict[str, str] = {
    "daily": "По дням",
    "weekly": "По неделям",
    "monthly": "По месяцам",
}


def resample_timeseries(
    df: pd.DataFrame,
    date_col: str,
    value_cols: list[str],
    granularity: Granularity = "daily",
    agg: str = "mean",
) -> pd.DataFrame:
    """Ресемплинг временного ряда по заданной гранулярности."""
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col).sort_index()
    freq = FREQ[granularity]
    result = df[value_cols].resample(freq).agg(agg)
    return result.reset_index()


def add_rolling_avg(
    df: pd.DataFrame,
    date_col: str,
    value_col: str,
    windows: list[int] | None = None,
) -> pd.DataFrame:
    """Добавить столбцы скользящего среднего MA7 / MA30."""
    if windows is None:
        windows = [7, 30]
    df = df.copy().sort_values(date_col)
    for w in windows:
        df[f"{value_col}_ma{w}"] = (
            df[value_col].rolling(window=w, min_periods=max(1, w // 3)).mean().round(2)
        )
    return df


def compute_momentum(
    df: pd.DataFrame,
    date_col: str,
    value_col: str,
    smooth_window: int = 7,
) -> pd.DataFrame:
    """Вычислить импульс (производную) метрики во времени."""
    df = df.copy().sort_values(date_col)
    df[f"{value_col}_delta"] = df[value_col].diff()
    df[f"{value_col}_momentum"] = (
        df[f"{value_col}_delta"].rolling(smooth_window, min_periods=1).mean().round(3)
    )
    return df


def normalize_0_100(s: pd.Series) -> pd.Series:
    """Min-max нормализация ряда в диапазон [0, 100]."""
    mn, mx = s.min(), s.max()
    if mx <= mn:
        return pd.Series(50.0, index=s.index, dtype=float)
    return ((s - mn) / (mx - mn) * 100).round(2)


def fill_date_gaps(
    df: pd.DataFrame,
    date_col: str,
    value_cols: list[str],
    freq: str = "D",
) -> pd.DataFrame:
    """Заполнить пропуски дат форвардной интерполяцией."""
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    if df.empty:
        return df
    full_idx = pd.date_range(df[date_col].min(), df[date_col].max(), freq=freq)
    df = df.set_index(date_col).reindex(full_idx)
    for col in value_cols:
        if col in df.columns:
            df[col] = df[col].interpolate(method="linear").ffill().bfill()
    return df.reset_index().rename(columns={"index": date_col})
