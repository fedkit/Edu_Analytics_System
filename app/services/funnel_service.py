"""Funnel computation helpers."""

from __future__ import annotations

import pandas as pd


def compute_funnel_stats(funnel_df: pd.DataFrame) -> pd.DataFrame:
    """
    Input: step, section, users
    Output: adds conversion_rate, drop_off_rate, drop_off_users
    """
    df = funnel_df.copy().sort_values("step").reset_index(drop=True)
    top = df.loc[0, "users"] if not df.empty and df.loc[0, "users"] > 0 else 1
    df["conversion_rate"]  = (df["users"] / top * 100).round(2)
    df["drop_off_users"]   = df["users"].shift(1).fillna(df["users"]) - df["users"]
    df["drop_off_rate"]    = (df["drop_off_users"] / df["users"].shift(1).fillna(df["users"]) * 100).round(2)
    df.loc[0, "drop_off_rate"]  = 0
    df.loc[0, "drop_off_users"] = 0
    return df


PAGE_SECTIONS = ["home", "course", "exam", "profile", "library", "schedule", "grades"]
