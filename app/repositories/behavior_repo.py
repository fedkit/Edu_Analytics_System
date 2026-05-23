"""ClickHouse repository — all behavioral event data queries."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import pandas as pd
import streamlit as st
from clickhouse_connect.driver.client import Client

from app.utils.cache import get_ttl
from app.utils.logger import get_logger

log = get_logger(__name__)


class BehaviorRepository:
    def __init__(self, client: Client) -> None:
        self.client = client

    def _read(self, sql: str, params: dict | None = None) -> pd.DataFrame:
        result = self.client.query(sql, parameters=params or {})
        return pd.DataFrame(result.result_rows, columns=result.column_names)

    # ── DAU / WAU / MAU ───────────────────────────────────────────────────────

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_dau_timeseries(_self, start: date, end: date) -> pd.DataFrame:
        return _self._read(
            """
            SELECT toDate(session_start) AS day,
                   uniq(user_id)         AS dau,
                   count()               AS sessions
            FROM edu_analytics.session
            WHERE session_start >= {start:Date}
              AND session_start <  {end:Date} + INTERVAL 1 DAY
            GROUP BY day
            ORDER BY day
            """,
            {"start": start, "end": end},
        )

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_wau_timeseries(_self, start: date, end: date) -> pd.DataFrame:
        return _self._read(
            """
            SELECT toMonday(toDate(session_start)) AS week,
                   uniq(user_id)                   AS wau,
                   count()                          AS sessions
            FROM edu_analytics.session
            WHERE session_start >= {start:Date}
              AND session_start <  {end:Date} + INTERVAL 1 DAY
            GROUP BY week
            ORDER BY week
            """,
            {"start": start, "end": end},
        )

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_mau_timeseries(_self, start: date, end: date) -> pd.DataFrame:
        return _self._read(
            """
            SELECT toStartOfMonth(toDate(session_start)) AS month,
                   uniq(user_id)                          AS mau,
                   count()                                AS sessions
            FROM edu_analytics.session
            WHERE session_start >= {start:Date}
              AND session_start <  {end:Date} + INTERVAL 1 DAY
            GROUP BY month
            ORDER BY month
            """,
            {"start": start, "end": end},
        )

    # ── Session metrics ───────────────────────────────────────────────────────

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_session_duration_timeseries(_self, start: date, end: date) -> pd.DataFrame:
        return _self._read(
            """
            SELECT toDate(session_start) AS day,
                   avg(dateDiff('minute', session_start, session_end)) AS avg_duration_min,
                   count() AS sessions
            FROM edu_analytics.session
            WHERE session_start >= {start:Date}
              AND session_start <  {end:Date} + INTERVAL 1 DAY
              AND session_end IS NOT NULL
            GROUP BY day
            ORDER BY day
            """,
            {"start": start, "end": end},
        )

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_behavior_kpis(_self, start: date, end: date) -> dict:
        row = _self._read(
            """
            SELECT
                uniq(user_id)   AS unique_users,
                count()         AS total_sessions,
                avg(dateDiff('minute', session_start, session_end)) AS avg_duration_min
            FROM edu_analytics.session
            WHERE session_start >= {start:Date}
              AND session_start <  {end:Date} + INTERVAL 1 DAY
              AND session_end IS NOT NULL
            """,
            {"start": start, "end": end},
        )
        evts = _self._read(
            """
            SELECT count() AS total_events
            FROM edu_analytics.event
            WHERE event_time >= {start:Date}
              AND event_time <  {end:Date} + INTERVAL 1 DAY
            """,
            {"start": start, "end": end},
        )
        result = row.iloc[0].to_dict() if not row.empty else {}
        result["total_events"] = int(evts.iloc[0]["total_events"]) if not evts.empty else 0
        # sessions per user
        result["sessions_per_user"] = (
            result["total_sessions"] / result["unique_users"]
            if result.get("unique_users")
            else 0
        )
        return result

    # ── Events ────────────────────────────────────────────────────────────────

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_events_timeseries(_self, start: date, end: date) -> pd.DataFrame:
        return _self._read(
            """
            SELECT toDate(event_time) AS day,
                   count()            AS events,
                   uniq(session_id)   AS sessions
            FROM edu_analytics.event
            WHERE event_time >= {start:Date}
              AND event_time <  {end:Date} + INTERVAL 1 DAY
            GROUP BY day
            ORDER BY day
            """,
            {"start": start, "end": end},
        )

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_event_type_trends(_self, start: date, end: date) -> pd.DataFrame:
        return _self._read(
            """
            SELECT toDate(event_time) AS day,
                   event_type,
                   count() AS events
            FROM edu_analytics.event
            WHERE event_time >= {start:Date}
              AND event_time <  {end:Date} + INTERVAL 1 DAY
            GROUP BY day, event_type
            ORDER BY day, event_type
            """,
            {"start": start, "end": end},
        )

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_top_pages(_self, start: date, end: date, limit: int = 20) -> pd.DataFrame:
        return _self._read(
            """
            SELECT p.page_name, p.page_section,
                   count(e.event_id) AS event_count,
                   uniq(e.session_id) AS session_count
            FROM edu_analytics.event e
            JOIN edu_analytics.page  p ON p.page_id = e.page_id
            WHERE e.event_time >= {start:Date}
              AND e.event_time <  {end:Date} + INTERVAL 1 DAY
            GROUP BY p.page_name, p.page_section
            ORDER BY event_count DESC
            LIMIT {limit:UInt32}
            """,
            {"start": start, "end": end, "limit": limit},
        )

    # ── Temporal heatmaps ─────────────────────────────────────────────────────

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_hourly_heatmap(_self, start: date, end: date) -> pd.DataFrame:
        """Sessions by day-of-week (0=Mon) and hour-of-day."""
        return _self._read(
            """
            SELECT toDayOfWeek(session_start) - 1 AS dow,
                   toHour(session_start)           AS hour,
                   count()                         AS sessions
            FROM edu_analytics.session
            WHERE session_start >= {start:Date}
              AND session_start <  {end:Date} + INTERVAL 1 DAY
            GROUP BY dow, hour
            ORDER BY dow, hour
            """,
            {"start": start, "end": end},
        )

    # ── Device breakdown ──────────────────────────────────────────────────────

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_device_breakdown(_self, start: date, end: date) -> pd.DataFrame:
        return _self._read(
            """
            SELECT device_type,
                   count()        AS sessions,
                   uniq(user_id)  AS users
            FROM edu_analytics.session
            WHERE session_start >= {start:Date}
              AND session_start <  {end:Date} + INTERVAL 1 DAY
            GROUP BY device_type
            ORDER BY sessions DESC
            """,
            {"start": start, "end": end},
        )

    # ── Navigation / Sankey ───────────────────────────────────────────────────

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_page_transitions(_self, start: date, end: date, limit: int = 30) -> pd.DataFrame:
        return _self._read(
            """
            SELECT p_from.page_name AS from_page,
                   p_to.page_name   AS to_page,
                   count()          AS transitions
            FROM edu_analytics.event e
            JOIN edu_analytics.page p_from ON p_from.page_id = e.page_id
            JOIN edu_analytics.page p_to   ON p_to.page_id   = e.next_page_id
            WHERE e.event_time >= {start:Date}
              AND e.event_time <  {end:Date} + INTERVAL 1 DAY
              AND e.next_page_id IS NOT NULL
            GROUP BY from_page, to_page
            ORDER BY transitions DESC
            LIMIT {limit:UInt32}
            """,
            {"start": start, "end": end, "limit": limit},
        )

    # ── Funnel ────────────────────────────────────────────────────────────────

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_funnel_data(_self, sections: list[str], start: date, end: date) -> pd.DataFrame:
        """Count unique users who visited each section (ordered funnel steps)."""
        rows = []
        for step, section in enumerate(sections, 1):
            r = _self._read(
                """
                SELECT count(DISTINCT s.user_id) AS users
                FROM edu_analytics.event  e
                JOIN edu_analytics.page   p ON p.page_id = e.page_id
                JOIN edu_analytics.session s ON s.session_id = e.session_id
                WHERE e.event_time >= {start:Date}
                  AND e.event_time <  {end:Date} + INTERVAL 1 DAY
                  AND p.page_section = {sec:String}
                """,
                {"start": start, "end": end, "sec": section},
            )
            users = int(r.iloc[0]["users"]) if not r.empty else 0
            rows.append({"step": step, "section": section, "users": users})
        return pd.DataFrame(rows)

    # ── Retention ─────────────────────────────────────────────────────────────

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_cohort_data(_self, start: date, end: date) -> pd.DataFrame:
        """Weekly cohort retention raw data: cohort_week, activity_week, users."""
        return _self._read(
            """
            WITH first_seen AS (
                SELECT user_id,
                       toMonday(min(toDate(session_start))) AS cohort_week
                FROM edu_analytics.session
                WHERE session_start >= {start:Date}
                  AND session_start <  {end:Date} + INTERVAL 1 DAY
                GROUP BY user_id
            ),
            activity AS (
                SELECT user_id,
                       toMonday(toDate(session_start)) AS activity_week
                FROM edu_analytics.session
                WHERE session_start >= {start:Date}
                  AND session_start <  {end:Date} + INTERVAL 1 DAY
                GROUP BY user_id, activity_week
            )
            SELECT f.cohort_week,
                   a.activity_week,
                   dateDiff('week', f.cohort_week, a.activity_week) AS week_number,
                   count(DISTINCT a.user_id) AS users
            FROM first_seen f
            JOIN activity a ON a.user_id = f.user_id
                            AND a.activity_week >= f.cohort_week
            GROUP BY f.cohort_week, a.activity_week, week_number
            ORDER BY f.cohort_week, week_number
            """,
            {"start": start, "end": end},
        )

    # ── Per-user behavioral summary (for correlation and RFM) ─────────────────

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_per_user_behavior(_self, start: date, end: date) -> pd.DataFrame:
        return _self._read(
            """
            SELECT s.user_id,
                   count(DISTINCT s.session_id)  AS session_count,
                   count(e.event_id)              AS event_count,
                   avg(dateDiff('minute', s.session_start, s.session_end)) AS avg_duration_min,
                   max(toDate(s.session_start))  AS last_active,
                   uniq(e.page_id)               AS unique_pages,
                   countIf(p.page_section = 'course')   AS course_views,
                   countIf(p.page_section = 'exam')     AS exam_views,
                   countIf(p.page_section = 'library')  AS library_views
            FROM edu_analytics.session s
            LEFT JOIN edu_analytics.event e ON e.session_id = s.session_id
            LEFT JOIN edu_analytics.page  p ON p.page_id    = e.page_id
            WHERE s.session_start >= {start:Date}
              AND s.session_start <  {end:Date} + INTERVAL 1 DAY
              AND s.session_end IS NOT NULL
            GROUP BY s.user_id
            """,
            {"start": start, "end": end},
        )

    # ── Stickiness (DAU/MAU ratio per month) ──────────────────────────────────

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_stickiness_timeseries(_self, start: date, end: date) -> pd.DataFrame:
        dau = _self.get_dau_timeseries(start, end)
        mau = _self.get_mau_timeseries(start, end)
        if dau.empty or mau.empty:
            return pd.DataFrame()
        dau["month"] = pd.to_datetime(dau["day"]).dt.to_period("M").dt.start_time
        mau["month"] = pd.to_datetime(mau["month"]).dt.to_period("M").dt.start_time
        merged = dau.merge(mau[["month", "mau"]], on="month", how="left")
        merged["stickiness"] = (merged["dau"] / merged["mau"] * 100).round(2)
        return merged

    # ── Sessions for a single user ────────────────────────────────────────────

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_sessions_for_user(_self, user_id: int) -> pd.DataFrame:
        return _self._read(
            """
            SELECT s.session_id,
                   toDate(s.session_start)    AS session_date,
                   s.session_start, s.session_end,
                   s.device_type,
                   dateDiff('minute', s.session_start, s.session_end) AS duration_min,
                   count(e.event_id) AS event_count
            FROM edu_analytics.session s
            LEFT JOIN edu_analytics.event e ON e.session_id = s.session_id
            WHERE s.user_id = {uid:UInt32}
              AND s.session_end IS NOT NULL
            GROUP BY s.session_id, session_date, s.session_start,
                     s.session_end, s.device_type
            ORDER BY s.session_start DESC
            LIMIT 500
            """,
            {"uid": user_id},
        )
