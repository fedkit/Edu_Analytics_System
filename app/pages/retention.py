"""Retention / Cohort Analysis page."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from app.components.charts import PLOTLY_CONFIG, cohort_heatmap, line_chart
from app.components.filters import FilterState
from app.repositories.behavior_repo import BehaviorRepository
from app.services.retention_service import build_cohort_sizes, build_retention_matrix


def render(f: FilterState, behavior: BehaviorRepository) -> None:
    st.title("🔄 Удержание (Retention)")
    st.caption(f"Период: {f.start_date} — {f.end_date}")

    with st.spinner("Загрузка когортных данных…"):
        cohort_raw = behavior.get_cohort_data(f.start_date, f.end_date)

    if cohort_raw.empty:
        st.info("Недостаточно данных для когортного анализа в выбранном периоде.")
        return

    retention = build_retention_matrix(cohort_raw)
    sizes     = build_cohort_sizes(cohort_raw)

    # ── Overview metrics ──────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    if not retention.empty and 1 in retention.columns:
        w1_avg = retention[1].mean()
        col1.metric("Ср. retention (неделя 1)", f"{w1_avg:.1f}%")
    if not retention.empty and 2 in retention.columns:
        w2_avg = retention[2].mean()
        col2.metric("Ср. retention (неделя 2)", f"{w2_avg:.1f}%")
    if not sizes.empty:
        col3.metric("Когорт всего", len(sizes))

    st.divider()

    # ── Cohort heatmap ────────────────────────────────────────────────────────
    st.subheader("Матрица удержания по когортам (еженедельно)")
    fig = cohort_heatmap(retention, title="Retention Matrix — % от размера когорты")
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    # ── Average retention by week ─────────────────────────────────────────────
    st.subheader("Средний Retention по номеру недели")
    avg_by_week = retention.mean(axis=0).reset_index()
    avg_by_week.columns = ["week_number", "avg_retention_pct"]
    avg_by_week = avg_by_week[avg_by_week["week_number"] <= 8]
    if not avg_by_week.empty:
        fig = line_chart(
            avg_by_week, "week_number", "avg_retention_pct",
            title="Средний retention по номеру недели",
            y_label="Retention (%)",
        )
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    # ── Cohort sizes ──────────────────────────────────────────────────────────
    st.subheader("Размеры когорт")
    if not sizes.empty:
        sizes_df = sizes.reset_index()
        sizes_df.columns = ["cohort_week", "users"]
        sizes_df["cohort_week"] = sizes_df["cohort_week"].astype(str)
        fig = line_chart(sizes_df, "cohort_week", "users",
                         title="Новые пользователи по когортам (неделя первого входа)",
                         y_label="Пользователи", area=True)
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    # ── Raw data toggle ───────────────────────────────────────────────────────
    with st.expander("Матрица (таблица)"):
        st.dataframe(retention.fillna("").style.background_gradient(cmap="Blues"),
                     use_container_width=True)
