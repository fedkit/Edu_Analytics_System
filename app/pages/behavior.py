"""Behavior Analytics page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.analytics.anomaly import add_anomaly_column
from app.components.charts import (
    PLOTLY_CONFIG, bar_chart, heatmap, line_chart, pie_chart, sankey_chart,
)
from app.components.filters import FilterState
from app.repositories.behavior_repo import BehaviorRepository
from app.services.trend_service import add_moving_average

DAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def render(f: FilterState, behavior: BehaviorRepository) -> None:
    st.title("🔍 Поведенческая аналитика")
    st.caption(f"Период: {f.start_date} — {f.end_date}")

    # ── Tab layout ─────────────────────────────────────────────────────────────
    tabs = st.tabs([
        "Сессии", "События", "Временные паттерны",
        "Устройства", "Навигация",
    ])

    # ─── TAB 1: Sessions ──────────────────────────────────────────────────────
    with tabs[0]:
        st.subheader("Тренды сессий")
        dau_ts   = behavior.get_dau_timeseries(f.start_date, f.end_date)
        dur_ts   = behavior.get_session_duration_timeseries(f.start_date, f.end_date)
        wau_ts   = behavior.get_wau_timeseries(f.start_date, f.end_date)
        mau_ts   = behavior.get_mau_timeseries(f.start_date, f.end_date)

        c1, c2 = st.columns(2)
        with c1:
            if not dau_ts.empty:
                dau_ts = add_moving_average(dau_ts, "dau", 7)
                fig = line_chart(
                    dau_ts, "day", "dau",
                    title="Уникальные пользователи в день (DAU)",
                    y_label="Пользователи",
                    ma_col="dau_ma7", area=True,
                )
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        with c2:
            if not dur_ts.empty:
                dur_ts = add_moving_average(dur_ts, "avg_duration_min", 7)
                fig = line_chart(
                    dur_ts, "day", "avg_duration_min",
                    title="Средняя длительность сессии (мин)",
                    y_label="Минуты",
                    ma_col="avg_duration_min_ma7",
                )
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        c3, c4 = st.columns(2)
        with c3:
            if not wau_ts.empty:
                fig = line_chart(wau_ts, "week", "wau", title="WAU (Weekly Active Users)",
                                 y_label="Пользователи", area=True)
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        with c4:
            if not mau_ts.empty:
                fig = line_chart(mau_ts, "month", "mau", title="MAU (Monthly Active Users)",
                                 y_label="Пользователи", area=True)
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        # Sessions vs DAU combined
        if not dau_ts.empty:
            st.subheader("Сессии vs Пользователи")
            fig = line_chart(dau_ts, "day", ["sessions", "dau"],
                             title="Сессии и активные пользователи по дням")
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    # ─── TAB 2: Events ────────────────────────────────────────────────────────
    with tabs[1]:
        st.subheader("Тренды событий")
        evt_ts    = behavior.get_events_timeseries(f.start_date, f.end_date)
        type_ts   = behavior.get_event_type_trends(f.start_date, f.end_date)
        top_pages = behavior.get_top_pages(f.start_date, f.end_date)

        if not evt_ts.empty:
            evt_ts = add_moving_average(evt_ts, "events", 7)
            evt_ts = add_anomaly_column(evt_ts, "events")
            fig = line_chart(
                evt_ts, "day", "events",
                title="Количество событий по дням",
                y_label="События",
                ma_col="events_ma7",
                anomaly_col="is_anomaly",
                area=True,
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        if not type_ts.empty:
            st.subheader("Типы событий по дням")
            pivot = type_ts.pivot_table(index="day", columns="event_type", values="events", aggfunc="sum").reset_index()
            event_cols = [c for c in pivot.columns if c != "day"]
            fig = line_chart(pivot, "day", event_cols, title="Распределение типов событий")
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        if not top_pages.empty:
            st.subheader(f"Топ-20 страниц по событиям")
            fig = bar_chart(
                top_pages.sort_values("event_count"),
                x="event_count", y="page_name",
                title="Самые посещаемые страницы",
                horizontal=True,
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

            st.subheader("Распределение по секциям")
            sec_agg = top_pages.groupby("page_section")["event_count"].sum().reset_index()
            fig = pie_chart(sec_agg, "page_section", "event_count",
                            title="Доля событий по секциям страниц")
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    # ─── TAB 3: Temporal patterns ─────────────────────────────────────────────
    with tabs[2]:
        st.subheader("Паттерны активности")
        hm = behavior.get_hourly_heatmap(f.start_date, f.end_date)

        if not hm.empty:
            fig = heatmap(
                hm, x_col="hour", y_col="dow", value_col="sessions",
                title="Тепловая карта: активность по дням недели и часам",
                x_labels=[str(h) for h in range(24)],
                y_labels=DAYS_RU,
                colorscale="YlOrRd",
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

            # Day-of-week bar
            dow_agg = hm.groupby("dow")["sessions"].sum().reset_index()
            dow_agg["day_name"] = dow_agg["dow"].map(lambda d: DAYS_RU[int(d)])
            fig = bar_chart(dow_agg, "day_name", "sessions",
                            title="Активность по дням недели")
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

            # Hour-of-day bar
            hour_agg = hm.groupby("hour")["sessions"].sum().reset_index()
            fig = bar_chart(hour_agg, "hour", "sessions",
                            title="Активность по часам дня")
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    # ─── TAB 4: Devices ───────────────────────────────────────────────────────
    with tabs[3]:
        st.subheader("Типы устройств")
        dev = behavior.get_device_breakdown(f.start_date, f.end_date)
        if not dev.empty:
            c1, c2 = st.columns(2)
            with c1:
                fig = pie_chart(dev, "device_type", "sessions",
                                title="Сессии по типу устройства")
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
            with c2:
                fig = bar_chart(dev, "device_type", "users",
                                title="Уникальные пользователи по устройству")
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    # ─── TAB 5: Navigation ────────────────────────────────────────────────────
    with tabs[4]:
        st.subheader("Пути навигации")
        trans = behavior.get_page_transitions(f.start_date, f.end_date, limit=40)
        if not trans.empty:
            fig = sankey_chart(trans)
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

            st.subheader("Топ переходов")
            st.dataframe(trans.head(20), use_container_width=True)
        else:
            st.info("Нет данных о переходах за выбранный период.")
