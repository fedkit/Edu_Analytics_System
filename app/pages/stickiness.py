"""Stickiness Analysis page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components.charts import PLOTLY_CONFIG, bar_chart, line_chart, pie_chart
from app.components.filters import FilterState
from app.repositories.behavior_repo import BehaviorRepository
from app.services.trend_service import add_moving_average


def render(f: FilterState, behavior: BehaviorRepository) -> None:
    st.title("📌 Sticky-фактор")
    st.caption(f"Период: {f.start_date} — {f.end_date}")
    st.info(
        "**Stickiness = DAU / MAU × 100%**  "
        "— чем выше, тем чаще пользователи возвращаются ежедневно."
    )

    with st.spinner("Загрузка данных…"):
        dau_ts  = behavior.get_dau_timeseries(f.start_date, f.end_date)
        mau_ts  = behavior.get_mau_timeseries(f.start_date, f.end_date)
        wau_ts  = behavior.get_wau_timeseries(f.start_date, f.end_date)
        stick   = behavior.get_stickiness_timeseries(f.start_date, f.end_date)
        dev     = behavior.get_device_breakdown(f.start_date, f.end_date)

    # ── KPI cards ─────────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    avg_dau = dau_ts["dau"].mean() if not dau_ts.empty else 0
    max_mau = mau_ts["mau"].max()  if not mau_ts.empty else 0
    max_wau = wau_ts["wau"].max()  if not wau_ts.empty else 0
    avg_st  = stick["stickiness"].mean() if not stick.empty and "stickiness" in stick.columns else 0

    col1.metric("Ср. DAU",       f"{avg_dau:,.0f}")
    col2.metric("Макс. WAU",     f"{max_wau:,.0f}")
    col3.metric("Макс. MAU",     f"{max_mau:,.0f}")
    col4.metric("Ср. Stickiness", f"{avg_st:.1f}%")

    st.divider()

    # ── Stickiness over time ──────────────────────────────────────────────────
    if not stick.empty and "stickiness" in stick.columns:
        st.subheader("Stickiness (DAU/MAU) по дням")
        stick = add_moving_average(stick, "stickiness", 7)
        fig = line_chart(
            stick, "day", "stickiness",
            title="Stickiness Factor (%)",
            y_label="DAU / MAU × 100 (%)",
            ma_col="stickiness_ma7",
        )
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    # ── DAU / WAU / MAU overlay ───────────────────────────────────────────────
    st.subheader("DAU / WAU / MAU на одном графике")
    if not dau_ts.empty:
        dau_ts["day"] = pd.to_datetime(dau_ts["day"])
    if not wau_ts.empty:
        wau_ts["week"] = pd.to_datetime(wau_ts["week"])
    if not mau_ts.empty:
        mau_ts["month"] = pd.to_datetime(mau_ts["month"])

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if not dau_ts.empty:
            fig = line_chart(dau_ts, "day", "dau", title="DAU", y_label="Пользователи", area=True)
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
    with col_b:
        if not wau_ts.empty:
            fig = line_chart(wau_ts, "week", "wau", title="WAU", y_label="Пользователи", area=True)
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
    with col_c:
        if not mau_ts.empty:
            fig = line_chart(mau_ts, "month", "mau", title="MAU", y_label="Пользователи", area=True)
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    st.divider()

    # ── Stickiness by device ──────────────────────────────────────────────────
    if not dev.empty:
        st.subheader("Сессии по типу устройства")
        fig = pie_chart(dev, "device_type", "sessions",
                        title="Распределение сессий по устройствам")
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
