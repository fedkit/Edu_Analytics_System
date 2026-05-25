"""Сервис поведенческой аналитики: временны́е ряды активности."""
from __future__ import annotations

from datetime import date

import pandas as pd
from clickhouse_connect.driver.client import Client

from app.core.metrics import engagement_index
from app.core.time_aggregation import (
    Granularity,
    add_rolling_avg,
    fill_date_gaps,
    resample_timeseries,
)
from app.queries import clickhouse_queries as ch_q


class UsageService:
    def __init__(self, client: Client) -> None:
        self.ch = client

    # ── Unified Engagement Index ──────────────────────────────────────────────

    def engagement_timeseries(
        self,
        start: date,
        end: date,
        granularity: Granularity = "daily",
        rolling: int = 7,
    ) -> pd.DataFrame:
        """
        Единый DataFrame: DAU, sessions, duration, events + composite index.
        Все метрики сглажены rolling-средним.
        """
        intensity = ch_q.daily_behavior_intensity(self.ch, start, end)
        if intensity.empty:
            return pd.DataFrame()

        value_cols = ["dau", "sessions", "avg_duration_min", "events",
                      "sessions_per_user", "events_per_session"]
        intensity = fill_date_gaps(intensity, "date", value_cols)

        if granularity != "daily":
            intensity = resample_timeseries(intensity, "date", value_cols, granularity)

        for col in ["dau", "sessions", "avg_duration_min", "events",
                    "sessions_per_user", "events_per_session"]:
            if col in intensity.columns:
                intensity = add_rolling_avg(intensity, "date", col, windows=[rolling, rolling * 4])

        # Composite Engagement Index
        intensity["engagement_index"] = engagement_index(
            intensity,
            dau_col="dau",
            sessions_col="sessions",
            duration_col="avg_duration_min",
            events_col="events",
        )
        intensity = add_rolling_avg(intensity, "date", "engagement_index", windows=[rolling])

        return intensity.reset_index(drop=True)

    # ── DAU / WAU / MAU тренды ────────────────────────────────────────────────

    def dau_wau_mau(
        self,
        start: date,
        end: date,
        rolling: int = 7,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Тренды DAU, WAU, MAU со скользящим средним."""
        dau = ch_q.daily_dau(self.ch, start, end)
        wau = ch_q.weekly_wau(self.ch, start, end)
        mau = ch_q.monthly_mau(self.ch, start, end)

        if not dau.empty:
            dau = add_rolling_avg(dau, "date", "dau", windows=[rolling])
        if not wau.empty:
            wau = add_rolling_avg(wau, "date", "wau", windows=[rolling])

        return dau, wau, mau

    # ── Feature adoption: использование разделов ──────────────────────────────

    def section_adoption(
        self,
        start: date,
        end: date,
        granularity: Granularity = "weekly",
        rolling: int = 7,
    ) -> pd.DataFrame:
        """Тренд использования каждого раздела сайта во времени."""
        raw = ch_q.daily_section_usage(self.ch, start, end)
        if raw.empty:
            return pd.DataFrame()

        rows = []
        for section, grp in raw.groupby("section"):
            grp = grp[["date", "visits", "unique_users"]].copy()
            grp = fill_date_gaps(grp, "date", ["visits", "unique_users"])
            if granularity != "daily":
                grp = resample_timeseries(grp, "date", ["visits", "unique_users"], granularity)
            grp = add_rolling_avg(grp, "date", "visits", windows=[rolling])
            grp["section"] = section
            rows.append(grp)

        return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()

    # ── Retention ─────────────────────────────────────────────────────────────

    def retention_matrix(self, start: date, end: date) -> pd.DataFrame:
        """Матрица retention (когорта × неделя)."""
        return ch_q.cohort_retention(self.ch, start, end)

    # ── Hourly heatmap ────────────────────────────────────────────────────────

    def hourly_heatmap(self, start: date, end: date) -> pd.DataFrame:
        return ch_q.hourly_heatmap(self.ch, start, end)

    # ── Page transitions (Sankey) ─────────────────────────────────────────────

    def page_transitions(self, start: date, end: date) -> pd.DataFrame:
        return ch_q.page_transitions(self.ch, start, end)

    # ── Stickiness: DAU/MAU ──────────────────────────────────────────────────

    def stickiness(self, start: date, end: date, rolling: int = 7) -> pd.DataFrame:
        """Коэффициент залипаемости DAU/MAU по дням."""
        dau = ch_q.daily_dau(self.ch, start, end)
        mau = ch_q.monthly_mau(self.ch, start, end)
        if dau.empty or mau.empty:
            return pd.DataFrame()

        dau["month"] = pd.to_datetime(dau["date"]).dt.to_period("M").dt.start_time
        mau["month"] = pd.to_datetime(mau["date"]).dt.to_period("M").dt.start_time
        df = dau.merge(mau[["month", "mau"]], on="month", how="left")
        df["stickiness"] = (df["dau"] / df["mau"] * 100).round(2)
        df = add_rolling_avg(df, "date", "stickiness", windows=[rolling])
        return df.reset_index(drop=True)
