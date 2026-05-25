"""Составные метрики: индекс вовлечённости, индекс успеваемости, сопряжение."""
from __future__ import annotations

import pandas as pd

from app.core.time_aggregation import normalize_0_100


def engagement_index(
    df: pd.DataFrame,
    dau_col: str = "dau",
    sessions_col: str = "sessions",
    duration_col: str = "avg_duration_min",
    events_col: str = "events",
    weights: tuple[float, float, float, float] = (0.30, 0.25, 0.25, 0.20),
) -> pd.Series:
    """Composite Engagement Index из 4 нормализованных поведенческих метрик."""
    cols = [dau_col, sessions_col, duration_col, events_col]
    normed = [normalize_0_100(df[c]) for c in cols if c in df.columns]
    if not normed:
        return pd.Series(dtype=float)
    actual_w = weights[: len(normed)]
    total = sum(actual_w)
    result = sum(n * (w / total) for n, w in zip(normed, actual_w))
    return result.round(2)


def academic_index(
    df: pd.DataFrame,
    gpa_col: str = "avg_score_pct",
    att_col: str = "attendance_pct",
    pass_col: str = "pass_rate",
    weights: tuple[float, float, float] = (0.40, 0.35, 0.25),
) -> pd.Series:
    """Composite Academic Performance Index из 3 нормализованных метрик."""
    parts = []
    w_used = []
    for col, w in zip([gpa_col, att_col, pass_col], weights):
        if col in df.columns:
            parts.append(normalize_0_100(df[col]))
            w_used.append(w)
    if not parts:
        return pd.Series(dtype=float)
    total = sum(w_used)
    return sum(p * (w / total) for p, w in zip(parts, w_used)).round(2)


def rolling_correlation(
    s1: pd.Series,
    s2: pd.Series,
    window: int = 30,
) -> pd.Series:
    """Скользящая корреляция Пирсона двух временных рядов."""
    return s1.rolling(window=window, min_periods=max(5, window // 3)).corr(s2).round(3)


def lag_correlation(
    target: pd.Series,
    predictor: pd.Series,
    max_lag: int = 21,
    step: int = 7,
) -> pd.DataFrame:
    """Корреляция между target и предиктором со сдвигом lag дней.

    Возвращает DataFrame с колонками: lag_days, correlation.
    """
    rows = []
    for lag in range(0, max_lag + 1, step):
        shifted = predictor.shift(lag)
        corr = target.corr(shifted)
        rows.append({"lag_days": lag, "correlation": round(corr, 3) if pd.notna(corr) else 0.0})
    return pd.DataFrame(rows)
