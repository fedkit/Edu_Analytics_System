"""Trend analysis: moving averages, growth rates, period comparison."""

from __future__ import annotations

import numpy as np
import pandas as pd


def add_moving_average(
    df: pd.DataFrame, col: str, window: int = 7, label: str | None = None
) -> pd.DataFrame:
    df = df.copy()
    out_col = label or f"{col}_ma{window}"
    df[out_col] = df[col].rolling(window, min_periods=1).mean().round(2)
    return df


def add_pct_change(df: pd.DataFrame, col: str) -> pd.DataFrame:
    df = df.copy()
    df[f"{col}_pct_change"] = df[col].pct_change() * 100
    return df


def period_summary(df: pd.DataFrame, value_col: str) -> dict:
    """Return basic stats dict for a time-series DataFrame column."""
    if df.empty or value_col not in df.columns:
        return {"mean": 0, "max": 0, "min": 0, "sum": 0}
    s = df[value_col].dropna()
    return {
        "mean": round(float(s.mean()), 2),
        "max":  round(float(s.max()), 2),
        "min":  round(float(s.min()), 2),
        "sum":  round(float(s.sum()), 2),
    }


def merge_current_previous(
    curr: pd.DataFrame,
    prev: pd.DataFrame,
    date_col: str,
    value_col: str,
    offset_days: int,
) -> pd.DataFrame:
    """
    Align two time series by shifting prev dates forward by offset_days,
    then merge on the shifted date to enable period comparison overlay.
    """
    if curr.empty or prev.empty:
        return curr
    prev = prev.copy()
    prev[date_col] = pd.to_datetime(prev[date_col]) + pd.Timedelta(days=offset_days)
    prev = prev.rename(columns={value_col: f"{value_col}_prev"})
    curr = curr.copy()
    curr[date_col] = pd.to_datetime(curr[date_col])
    return curr.merge(prev[[date_col, f"{value_col}_prev"]], on=date_col, how="left")


def compute_trend_direction(series: pd.Series, window: int = 7) -> str:
    """Return '↑', '↓', or '→' based on recent slope."""
    recent = series.dropna().tail(window)
    if len(recent) < 2:
        return "→"
    slope = np.polyfit(range(len(recent)), recent, 1)[0]
    if slope > 0.01 * recent.mean():
        return "↑"
    elif slope < -0.01 * recent.mean():
        return "↓"
    return "→"
