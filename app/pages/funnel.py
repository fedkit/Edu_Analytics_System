"""Funnel Analysis page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components.charts import PLOTLY_CONFIG, bar_chart, funnel_chart, line_chart
from app.components.filters import FilterState
from app.repositories.behavior_repo import BehaviorRepository
from app.services.funnel_service import PAGE_SECTIONS, compute_funnel_stats
from app.utils.helpers import previous_period


def render(f: FilterState, behavior: BehaviorRepository) -> None:
    st.title("🎯 Воронки")
    st.caption(f"Период: {f.start_date} — {f.end_date}")

    st.markdown(
        "Постройте воронку, выбрав шаги в нужном порядке. "
        "Каждый шаг — секция страницы."
    )

    # ── Funnel builder ────────────────────────────────────────────────────────
    col1, col2 = st.columns([1, 3])
    with col1:
        selected_steps = st.multiselect(
            "Шаги воронки (по порядку)",
            options=PAGE_SECTIONS,
            default=["home", "course", "exam"],
            key="funnel_steps",
        )

    if not selected_steps:
        st.warning("Выберите хотя бы два шага для построения воронки.")
        return

    with st.spinner("Вычисление воронки…"):
        raw = behavior.get_funnel_data(selected_steps, f.start_date, f.end_date)

    if raw.empty or raw["users"].max() == 0:
        st.info("Нет данных для выбранных шагов в этом периоде.")
        return

    funnel_df = compute_funnel_stats(raw)

    # ── Main funnel chart ─────────────────────────────────────────────────────
    col_f, col_t = st.columns([3, 2])
    with col_f:
        fig = funnel_chart(funnel_df, "section", "users", title="Воронка пользователей")
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    with col_t:
        st.subheader("Метрики воронки")
        display = funnel_df[["step", "section", "users", "conversion_rate", "drop_off_rate"]].copy()
        display.columns = ["Шаг", "Секция", "Пользователи", "Конверсия (%)", "Отток (%)"]
        st.dataframe(display, use_container_width=True, hide_index=True)

    st.divider()

    # ── Drop-off bar ──────────────────────────────────────────────────────────
    st.subheader("Отток по шагам")
    fig = bar_chart(
        funnel_df[funnel_df["step"] > 1],
        x="section", y="drop_off_rate",
        title="Доля отпавших пользователей на каждом шаге (%)",
    )
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    st.divider()

    # ── Period comparison ─────────────────────────────────────────────────────
    if f.comparison != "none":
        st.subheader("Сравнение с предыдущим периодом")
        prev_start, prev_end = previous_period(f.start_date, f.end_date)
        raw_prev = behavior.get_funnel_data(selected_steps, prev_start, prev_end)
        if not raw_prev.empty:
            prev_funnel = compute_funnel_stats(raw_prev)
            compare = funnel_df[["section", "users"]].merge(
                prev_funnel[["section", "users"]].rename(columns={"users": "users_prev"}),
                on="section", how="left",
            )
            fig = bar_chart(
                compare, x="section", y=["users", "users_prev"],
                title="Пользователи: текущий vs предыдущий период",
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
