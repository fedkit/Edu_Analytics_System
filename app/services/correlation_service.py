"""Correlation analytics between behavior and academic performance."""

from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd
from scipy import stats


def compute_correlation(
    x: pd.Series, y: pd.Series, method: str = "pearson"
) -> Tuple[float, float]:
    """Return (correlation coefficient, p-value)."""
    mask = x.notna() & y.notna()
    x, y = x[mask], y[mask]
    if len(x) < 5:
        return 0.0, 1.0
    if method == "spearman":
        r, p = stats.spearmanr(x, y)
    else:
        r, p = stats.pearsonr(x, y)
    return round(float(r), 4), round(float(p), 4)


def build_correlation_matrix(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Full pairwise Pearson correlation matrix."""
    return df[cols].corr(method="pearson").round(3)


def rolling_correlation(
    df: pd.DataFrame, col_x: str, col_y: str,
    date_col: str, window: int = 30
) -> pd.DataFrame:
    """
    Compute rolling Pearson correlation over a sliding window (days).
    Returns DataFrame with date and rolling_corr columns.
    """
    df = df.copy().sort_values(date_col)
    df[date_col] = pd.to_datetime(df[date_col])

    results = []
    dates = df[date_col].unique()
    for i in range(window, len(dates) + 1):
        window_dates = dates[i - window : i]
        subset = df[df[date_col].isin(window_dates)]
        x, y = subset[col_x].dropna(), subset[col_y].dropna()
        idx = subset[[col_x, col_y]].dropna()
        if len(idx) >= 5:
            r, _ = stats.pearsonr(idx[col_x], idx[col_y])
        else:
            r = np.nan
        results.append({"date": dates[i - 1], "rolling_corr": round(float(r), 4) if not np.isnan(r) else None})
    return pd.DataFrame(results)


def generate_insight(
    x_label: str, y_label: str, corr: float, threshold_sessions: float = 5.0
) -> str:
    """Generate a human-readable insight string."""
    strength = (
        "очень сильная" if abs(corr) > 0.7
        else "умеренная" if abs(corr) > 0.4
        else "слабая"
    )
    direction = "положительная" if corr >= 0 else "отрицательная"
    return (
        f"Корреляция между {x_label} и {y_label}: "
        f"{strength} {direction} (r={corr:+.3f})"
    )
