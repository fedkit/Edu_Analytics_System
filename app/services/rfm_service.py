"""RFM segmentation for educational analytics."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd


SEGMENT_LABELS = {
    (3, 3, 3): "Champions",
    (3, 3, 2): "Champions",
    (3, 2, 3): "Loyal Users",
    (2, 3, 3): "Loyal Users",
    (3, 3, 1): "Loyal Users",
    (2, 2, 3): "Potential Loyalists",
    (3, 1, 2): "Potential Loyalists",
    (1, 3, 3): "Silent High Performers",
    (1, 2, 3): "Silent High Performers",
    (2, 3, 1): "At Risk",
    (2, 1, 2): "At Risk",
    (1, 1, 3): "Engaged Struggling",
    (3, 1, 1): "Crammers",
    (2, 1, 1): "Potential Dropouts",
    (1, 2, 1): "Potential Dropouts",
    (1, 1, 1): "Potential Dropouts",
    (1, 1, 2): "Potential Dropouts",
}

SEGMENT_COLORS = {
    "Champions":           "#2ecc71",
    "Loyal Users":         "#27ae60",
    "Potential Loyalists": "#3498db",
    "Silent High Performers": "#9b59b6",
    "At Risk":             "#e67e22",
    "Engaged Struggling":  "#e74c3c",
    "Crammers":            "#f39c12",
    "Potential Dropouts":  "#c0392b",
}


def compute_rfm(
    behavior: pd.DataFrame,
    academic: pd.DataFrame,
    ref_date: date,
) -> pd.DataFrame:
    """
    Merge behavioral and academic data into an RFM frame.

    behavior: user_id, session_count, event_count, last_active,
              course_views, exam_views, library_views, avg_duration_min
    academic: user_id, avg_score_pct, att_pct
    """
    if behavior.empty:
        return pd.DataFrame()

    df = behavior.copy()
    df["last_active"] = pd.to_datetime(df["last_active"]).dt.date
    ref = pd.Timestamp(ref_date).date()
    df["recency_days"] = df["last_active"].apply(
        lambda d: (ref - d).days if pd.notna(d) else 999
    )

    # R = recency (lower days = higher score)
    # F = frequency (session_count)
    # M = educational value = weighted composite
    if not academic.empty:
        df = df.merge(academic[["user_id", "avg_score_pct", "att_pct"]], on="user_id", how="left")
    else:
        df["avg_score_pct"] = 50.0
        df["att_pct"]       = 50.0

    df["avg_score_pct"] = df["avg_score_pct"].fillna(50.0)
    df["att_pct"]       = df["att_pct"].fillna(50.0)

    # Monetary proxy: weighted educational engagement
    df["monetary"] = (
        0.30 * df["avg_score_pct"].clip(0, 100) +
        0.20 * df["att_pct"].clip(0, 100) +
        0.20 * np.log1p(df.get("course_views", 0)).clip(0, 10) * 10 +
        0.15 * np.log1p(df.get("exam_views", 0)).clip(0, 10) * 10 +
        0.15 * np.log1p(df.get("event_count", 0)).clip(0, 10) * 10
    )

    # Score each dimension 1–3
    df["r_score"] = _quantile_score(df["recency_days"],   ascending=False)
    df["f_score"] = _quantile_score(df["session_count"],  ascending=True)
    df["m_score"] = _quantile_score(df["monetary"],       ascending=True)

    df["rfm_segment"] = df.apply(
        lambda row: SEGMENT_LABELS.get(
            (int(row["r_score"]), int(row["f_score"]), int(row["m_score"])),
            "Potential Dropouts",
        ),
        axis=1,
    )
    df["rfm_score"] = df["r_score"] + df["f_score"] + df["m_score"]
    return df


def _quantile_score(series: pd.Series, ascending: bool = True) -> pd.Series:
    """Map series to 1-3 score using terciles."""
    q33 = series.quantile(0.33)
    q66 = series.quantile(0.66)
    if ascending:
        return series.apply(
            lambda x: 1 if x <= q33 else (2 if x <= q66 else 3)
        )
    else:
        return series.apply(
            lambda x: 3 if x <= q33 else (2 if x <= q66 else 1)
        )
