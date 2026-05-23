"""Main Dashboard — KPI overview with trend charts."""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

from app.analytics.anomaly import add_anomaly_column
from app.analytics.kpi import build_academic_kpis, build_behavior_kpis
from app.components.charts import PLOTLY_CONFIG, bar_chart, line_chart
from app.components.filters import FilterState
from app.components.kpi_card import render_kpi_row
from app.repositories.academic_repo import AcademicRepository
from app.repositories.behavior_repo import BehaviorRepository
from app.services.trend_service import add_moving_average, add_pct_change, period_summary
from app.utils.helpers import previous_period


def render(
    f: FilterState,
    academic: AcademicRepository,
    behavior: BehaviorRepository,
) -> None:
    st.title("📊 Главный дашборд")
    st.caption(f"Период: {f.start_date} — {f.end_date}")

    prev_start, prev_end = previous_period(f.start_date, f.end_date)

    # ── Load data ─────────────────────────────────────────────────────────────
    with st.spinner("Загрузка данных…"):
        curr_beh  = behavior.get_behavior_kpis(f.start_date, f.end_date)
        prev_beh  = behavior.get_behavior_kpis(prev_start, prev_end)
        curr_acad = academic.get_academic_kpis(f.start_date, f.end_date)
        prev_acad = academic.get_academic_kpis(prev_start, prev_end)

        dau_ts   = behavior.get_dau_timeseries(f.start_date, f.end_date)
        gpa_ts   = academic.get_gpa_timeseries(f.start_date, f.end_date)
        att_ts   = academic.get_attendance_timeseries(f.start_date, f.end_date)
        pass_ts  = academic.get_pass_rate_timeseries(f.start_date, f.end_date)
        sess_ts  = behavior.get_session_duration_timeseries(f.start_date, f.end_date)

    # ── MAU / WAU quick numbers ───────────────────────────────────────────────
    mau_df = behavior.get_mau_timeseries(f.start_date, f.end_date)
    wau_df = behavior.get_wau_timeseries(f.start_date, f.end_date)
    curr_beh["mau"] = int(mau_df["mau"].max()) if not mau_df.empty else 0
    curr_beh["wau"] = int(wau_df["wau"].max()) if not wau_df.empty else 0
    curr_beh["dau"] = int(dau_ts["dau"].mean().round()) if not dau_ts.empty else 0

    prev_mau = behavior.get_mau_timeseries(prev_start, prev_end)
    prev_wau = behavior.get_wau_timeseries(prev_start, prev_end)
    prev_dau = behavior.get_dau_timeseries(prev_start, prev_end)
    prev_beh["mau"] = int(prev_mau["mau"].max()) if not prev_mau.empty else 0
    prev_beh["wau"] = int(prev_wau["wau"].max()) if not prev_wau.empty else 0
    prev_beh["dau"] = int(prev_dau["dau"].mean().round()) if not prev_dau.empty else 0

    # ── Behavior KPIs ──────────────────────────────────────────────────────────
    st.subheader("Поведение пользователей")
    beh_kpis = build_behavior_kpis(curr_beh, prev_beh)
    render_kpi_row(beh_kpis)

    # ── Academic KPIs ─────────────────────────────────────────────────────────
    st.subheader("Академическая успеваемость")
    acad_kpis = build_academic_kpis(curr_acad, prev_acad)
    render_kpi_row(acad_kpis)

    st.divider()

    # ── Trend charts ─────────────────────────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        if not dau_ts.empty:
            dau_ts = add_moving_average(dau_ts, "dau", window=7)
            dau_ts = add_anomaly_column(dau_ts, "dau")
            fig = line_chart(
                dau_ts, x="day", y="dau",
                title="DAU (Daily Active Users)",
                y_label="Уникальные пользователи",
                ma_col="dau_ma7",
                anomaly_col="is_anomaly",
                area=True,
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        else:
            st.info("Нет данных DAU за выбранный период.")

    with col2:
        if not gpa_ts.empty:
            gpa_ts = add_moving_average(gpa_ts, "avg_score_pct", window=7)
            fig = line_chart(
                gpa_ts, x="score_date", y="avg_score_pct",
                title="Средний балл (%) — тренд",
                y_label="Балл (%)",
                ma_col="avg_score_pct_ma7",
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        else:
            st.info("Нет данных GPA.")

    col3, col4 = st.columns(2)

    with col3:
        if not att_ts.empty:
            att_ts = add_moving_average(att_ts, "attendance_pct", window=7)
            fig = line_chart(
                att_ts, x="lesson_date", y="attendance_pct",
                title="Посещаемость (%) — тренд",
                y_label="Посещаемость (%)",
                ma_col="attendance_pct_ma7",
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        else:
            st.info("Нет данных посещаемости.")

    with col4:
        if not pass_ts.empty:
            pass_ts = add_moving_average(pass_ts, "pass_rate", window=7)
            fig = line_chart(
                pass_ts, x="score_date", y="pass_rate",
                title="Pass Rate (%) — тренд",
                y_label="Доля сдавших (%)",
                ma_col="pass_rate_ma7",
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        else:
            st.info("Нет данных pass rate.")

    st.divider()

    # ── Sessions overview ──────────────────────────────────────────────────────
    st.subheader("Активность сессий")
    if not dau_ts.empty:
        fig = line_chart(
            dau_ts, x="day", y="sessions",
            title="Количество сессий по дням",
            y_label="Сессии",
            area=True,
        )
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    # ── GPA by faculty ─────────────────────────────────────────────────────────
    st.subheader("Средний балл по факультетам")
    fac_gpa = academic.get_gpa_by_faculty(f.start_date, f.end_date)
    if not fac_gpa.empty:
        fig = bar_chart(
            fac_gpa.sort_values("avg_score_pct"),
            x="avg_score_pct", y="faculty_name",
            title="Средний балл по факультетам",
            horizontal=True,
        )
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
