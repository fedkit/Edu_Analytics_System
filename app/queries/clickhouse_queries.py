"""ClickHouse запросы — временны́е ряды поведенческих данных."""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st
from clickhouse_connect.driver.client import Client


def _q(client: Client, sql: str, params: dict | None = None) -> pd.DataFrame:
    result = client.query(sql, parameters=params or {})
    return pd.DataFrame(result.result_rows, columns=result.column_names)


# ── Активные пользователи ─────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def daily_dau(_ch: Client, start: date, end: date) -> pd.DataFrame:
    """DAU по дням."""
    return _q(
        _ch,
        """
        SELECT toDate(session_start)   AS date,
               uniq(user_id)           AS dau,
               count()                 AS sessions,
               avg(dateDiff('minute', session_start, session_end)) AS avg_duration_min
        FROM edu_analytics.session
        WHERE session_start >= {start:Date}
          AND session_start <  {end:Date} + INTERVAL 1 DAY
          AND session_end IS NOT NULL
        GROUP BY date
        ORDER BY date
        """,
        {"start": start, "end": end},
    )


@st.cache_data(ttl=300, show_spinner=False)
def weekly_wau(_ch: Client, start: date, end: date) -> pd.DataFrame:
    """WAU по неделям."""
    return _q(
        _ch,
        """
        SELECT toMonday(toDate(session_start)) AS date,
               uniq(user_id)                   AS wau,
               count()                          AS sessions
        FROM edu_analytics.session
        WHERE session_start >= {start:Date}
          AND session_start <  {end:Date} + INTERVAL 1 DAY
        GROUP BY date
        ORDER BY date
        """,
        {"start": start, "end": end},
    )


@st.cache_data(ttl=300, show_spinner=False)
def monthly_mau(_ch: Client, start: date, end: date) -> pd.DataFrame:
    """MAU по месяцам."""
    return _q(
        _ch,
        """
        SELECT toStartOfMonth(toDate(session_start)) AS date,
               uniq(user_id)                          AS mau,
               count()                                AS sessions
        FROM edu_analytics.session
        WHERE session_start >= {start:Date}
          AND session_start <  {end:Date} + INTERVAL 1 DAY
        GROUP BY date
        ORDER BY date
        """,
        {"start": start, "end": end},
    )


# ── Поведенческая интенсивность ───────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def daily_behavior_intensity(_ch: Client, start: date, end: date) -> pd.DataFrame:
    """Сессий/пользователь, событий/сессию по дням."""
    return _q(
        _ch,
        """
        SELECT s.date,
               s.sessions,
               s.dau,
               round(s.sessions / nullIf(s.dau, 0), 2)   AS sessions_per_user,
               e.events,
               round(e.events   / nullIf(s.sessions, 0), 2) AS events_per_session,
               s.avg_duration_min
        FROM (
            SELECT toDate(session_start)   AS date,
                   count()                 AS sessions,
                   uniq(user_id)           AS dau,
                   avg(dateDiff('minute', session_start, session_end)) AS avg_duration_min
            FROM edu_analytics.session
            WHERE session_start >= {start:Date}
              AND session_start <  {end:Date} + INTERVAL 1 DAY
              AND session_end IS NOT NULL
            GROUP BY date
        ) s
        LEFT JOIN (
            SELECT toDate(event_time) AS date, count() AS events
            FROM edu_analytics.event
            WHERE event_time >= {start:Date}
              AND event_time <  {end:Date} + INTERVAL 1 DAY
            GROUP BY date
        ) e ON e.date = s.date
        ORDER BY s.date
        """,
        {"start": start, "end": end},
    )


# ── Использование разделов (feature adoption) ──────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def daily_section_usage(_ch: Client, start: date, end: date) -> pd.DataFrame:
    """Количество посещений каждого раздела по дням."""
    return _q(
        _ch,
        """
        SELECT toDate(e.event_time) AS date,
               p.page_section       AS section,
               count()              AS visits,
               uniq(s.user_id)      AS unique_users
        FROM edu_analytics.event e
        JOIN edu_analytics.page    p ON p.page_id    = e.page_id
        JOIN edu_analytics.session s ON s.session_id = e.session_id
        WHERE e.event_time >= {start:Date}
          AND e.event_time <  {end:Date} + INTERVAL 1 DAY
        GROUP BY date, section
        ORDER BY date, section
        """,
        {"start": start, "end": end},
    )


# ── Тепловая карта активности ─────────────────────────────────────────────────

@st.cache_data(ttl=600, show_spinner=False)
def hourly_heatmap(_ch: Client, start: date, end: date) -> pd.DataFrame:
    """Сессии по дням недели и часам."""
    return _q(
        _ch,
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


# ── Retention когорт ──────────────────────────────────────────────────────────

@st.cache_data(ttl=600, show_spinner=False)
def cohort_retention(_ch: Client, start: date, end: date) -> pd.DataFrame:
    """Недельный retention: когорта, номер недели, % удержания."""
    return _q(
        _ch,
        """
        WITH first_seen AS (
            SELECT user_id,
                   toMonday(min(toDate(session_start))) AS cohort_week
            FROM edu_analytics.session
            WHERE session_start >= {start:Date}
              AND session_start <  {end:Date} + INTERVAL 1 DAY
            GROUP BY user_id
        ),
        cohort_sizes AS (
            SELECT cohort_week, count() AS cohort_size
            FROM first_seen GROUP BY cohort_week
        ),
        activity AS (
            SELECT user_id,
                   toMonday(toDate(session_start)) AS activity_week
            FROM edu_analytics.session
            WHERE session_start >= {start:Date}
              AND session_start <  {end:Date} + INTERVAL 1 DAY
            GROUP BY user_id, activity_week
        )
        SELECT f.cohort_week AS cohort_week,
               dateDiff('week', f.cohort_week, a.activity_week) AS week_num,
               round(count(DISTINCT a.user_id) * 100.0 / cs.cohort_size, 1) AS retention_pct
        FROM first_seen f
        JOIN activity a ON a.user_id = f.user_id AND a.activity_week >= f.cohort_week
        JOIN cohort_sizes cs ON cs.cohort_week = f.cohort_week
        WHERE cs.cohort_size >= 5
        GROUP BY f.cohort_week, week_num, cs.cohort_size
        HAVING week_num <= 12
        ORDER BY f.cohort_week, week_num
        """,
        {"start": start, "end": end},
    )


# ── Переходы между страницами (Sankey) ────────────────────────────────────────

@st.cache_data(ttl=600, show_spinner=False)
def page_transitions(_ch: Client, start: date, end: date, limit: int = 40) -> pd.DataFrame:
    return _q(
        _ch,
        """
        SELECT p_from.page_section AS from_section,
               p_to.page_section   AS to_section,
               count()             AS transitions
        FROM edu_analytics.event e
        JOIN edu_analytics.page p_from ON p_from.page_id = e.page_id
        JOIN edu_analytics.page p_to   ON p_to.page_id   = e.next_page_id
        WHERE e.event_time >= {start:Date}
          AND e.event_time <  {end:Date} + INTERVAL 1 DAY
          AND e.next_page_id IS NOT NULL
        GROUP BY from_section, to_section
        ORDER BY transitions DESC
        LIMIT {limit:UInt32}
        """,
        {"start": start, "end": end, "limit": limit},
    )


# ── Per-user behavioral summary (для корреляции) ──────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def per_user_behavior(_ch: Client, start: date, end: date) -> pd.DataFrame:
    return _q(
        _ch,
        """
        SELECT s.user_id,
               count(DISTINCT s.session_id)  AS session_count,
               count(e.event_id)              AS event_count,
               avg(dateDiff('minute', s.session_start, s.session_end)) AS avg_duration_min,
               max(toDate(s.session_start))  AS last_active
        FROM edu_analytics.session s
        LEFT JOIN edu_analytics.event e ON e.session_id = s.session_id
        WHERE s.session_start >= {start:Date}
          AND s.session_start <  {end:Date} + INTERVAL 1 DAY
          AND s.session_end IS NOT NULL
        GROUP BY s.user_id
        """,
        {"start": start, "end": end},
    )


@st.cache_data(ttl=300, show_spinner=False)
def per_user_behavior_extended(_ch: Client, start: date, end: date) -> pd.DataFrame:
    """Extended per-user behavioral summary with more metrics."""
    period_days = max((end - start).days + 1, 1)
    return _q(
        _ch,
        """
        SELECT s.user_id,
               count(DISTINCT s.session_id)                                     AS session_count,
               count(e.event_id)                                                AS event_count,
               avg(dateDiff('minute', s.session_start, s.session_end))          AS avg_duration_min,
               count(DISTINCT toDate(s.session_start))                          AS active_days,
               count(DISTINCT e.page_id)                                        AS unique_pages,
               round(count(e.event_id) / nullIf(count(DISTINCT s.session_id),0), 2) AS events_per_session,
               count(DISTINCT s.session_id) / toFloat64({days:UInt32}) * 7     AS sessions_per_week
        FROM edu_analytics.session s
        LEFT JOIN edu_analytics.event e ON e.session_id = s.session_id
        WHERE s.session_start >= {start:Date}
          AND s.session_start <  {end:Date} + INTERVAL 1 DAY
          AND s.session_end IS NOT NULL
        GROUP BY s.user_id
        HAVING session_count > 0
        """,
        {"start": start, "end": end, "days": period_days},
    )


@st.cache_data(ttl=300, show_spinner=False)
def per_user_weekly_behavior(_ch: Client, start: date, end: date) -> pd.DataFrame:
    """Per-user per-week: sessions, events, active_days, avg_duration."""
    return _q(
        _ch,
        """
        SELECT s.user_id,
               toMonday(toDate(s.session_start))                              AS week,
               count(DISTINCT s.session_id)                                   AS sessions,
               count(e.event_id)                                              AS events,
               count(DISTINCT toDate(s.session_start))                       AS active_days,
               avg(dateDiff('minute', s.session_start, s.session_end))        AS avg_duration_min
        FROM edu_analytics.session s
        LEFT JOIN edu_analytics.event e ON e.session_id = s.session_id
        WHERE s.session_start >= {start:Date}
          AND s.session_start <  {end:Date} + INTERVAL 1 DAY
          AND s.session_end IS NOT NULL
        GROUP BY s.user_id, week
        ORDER BY s.user_id, week
        """,
        {"start": start, "end": end},
    )


@st.cache_data(ttl=300, show_spinner=False)
def per_user_page_behavior(_ch: Client, start: date, end: date) -> pd.DataFrame:
    """Per-user per-section: event count (for page impact analysis)."""
    return _q(
        _ch,
        """
        SELECT s.user_id,
               p.page_section,
               count(e.event_id) AS visits
        FROM edu_analytics.event e
        JOIN edu_analytics.session s ON s.session_id = e.session_id
        JOIN edu_analytics.page   p ON p.page_id    = e.page_id
        WHERE e.event_time >= {start:Date}
          AND e.event_time <  {end:Date} + INTERVAL 1 DAY
        GROUP BY s.user_id, p.page_section
        """,
        {"start": start, "end": end},
    )


@st.cache_data(ttl=300, show_spinner=False)
def weekly_behavior_agg(_ch: Client, start: date, end: date) -> pd.DataFrame:
    """Weekly aggregate behavioral metrics for time-series analysis."""
    return _q(
        _ch,
        """
        SELECT toMonday(toDate(s.session_start)) AS week,
               uniq(s.user_id)                   AS dau,
               count(DISTINCT s.session_id)       AS sessions,
               avg(dateDiff('minute', s.session_start, s.session_end)) AS avg_duration_min,
               count(e.event_id)                  AS events
        FROM edu_analytics.session s
        LEFT JOIN edu_analytics.event e ON e.session_id = s.session_id
        WHERE s.session_start >= {start:Date}
          AND s.session_start <  {end:Date} + INTERVAL 1 DAY
          AND s.session_end IS NOT NULL
        GROUP BY week
        ORDER BY week
        """,
        {"start": start, "end": end},
    )
