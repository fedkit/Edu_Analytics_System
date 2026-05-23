"""Weekly cohort retention matrix computation."""

from __future__ import annotations

import pandas as pd


def build_retention_matrix(cohort_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Input: cohort_week, week_number, users (raw from BehaviorRepository)
    Output: pivot table with cohort_week as index, week_number as columns,
            values = retention % (relative to cohort size at week 0).
    """
    if cohort_raw.empty:
        return pd.DataFrame()

    cohort_raw = cohort_raw.copy()
    cohort_raw["cohort_week"] = pd.to_datetime(cohort_raw["cohort_week"])

    # Cohort sizes (week 0)
    cohort_sizes = (
        cohort_raw[cohort_raw["week_number"] == 0]
        .set_index("cohort_week")["users"]
    )

    pivot = cohort_raw.pivot_table(
        index="cohort_week", columns="week_number", values="users", aggfunc="sum"
    )

    # Normalise by cohort size
    retention_pct = pivot.div(cohort_sizes, axis=0) * 100
    return retention_pct.round(1)


def build_cohort_sizes(cohort_raw: pd.DataFrame) -> pd.Series:
    if cohort_raw.empty:
        return pd.Series(dtype=float)
    return (
        cohort_raw[cohort_raw["week_number"] == 0]
        .set_index("cohort_week")["users"]
    )
