"""RFM Segmentation page."""

from __future__ import annotations

import plotly.express as px
import pandas as pd
import streamlit as st

from app.components.charts import PLOTLY_CONFIG, bar_chart, scatter_chart
from app.components.filters import FilterState
from app.repositories.academic_repo import AcademicRepository
from app.repositories.behavior_repo import BehaviorRepository
from app.services.rfm_service import SEGMENT_COLORS, compute_rfm


def render(
    f: FilterState,
    behavior: BehaviorRepository,
    academic: AcademicRepository,
) -> None:
    st.title("🎲 RFM-анализ")
    st.caption(f"Период: {f.start_date} — {f.end_date}")
    st.info(
        "**R** (Recency) — дней с последнего входа  "
        "**F** (Frequency) — количество сессий  "
        "**M** (Monetary) — учебная ценность: баллы + посещаемость + активность"
    )

    with st.spinner("Вычисление RFM…"):
        beh_df  = behavior.get_per_user_behavior(f.start_date, f.end_date)
        acad_df = academic.get_per_user_academic_summary(f.start_date, f.end_date)
        rfm_df  = compute_rfm(beh_df, acad_df, ref_date=f.end_date)

    if rfm_df.empty:
        st.info("Нет данных за выбранный период.")
        return

    # ── Segment overview ──────────────────────────────────────────────────────
    st.subheader("Распределение сегментов")
    seg_counts = (
        rfm_df.groupby("rfm_segment")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    seg_counts["color"] = seg_counts["rfm_segment"].map(SEGMENT_COLORS)

    col1, col2 = st.columns([2, 1])
    with col1:
        fig = px.bar(
            seg_counts, x="rfm_segment", y="count",
            color="rfm_segment",
            color_discrete_map=SEGMENT_COLORS,
            title="Количество студентов по сегменту",
        )
        fig.update_layout(showlegend=False, margin=dict(l=40, r=20, t=50, b=80))
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    with col2:
        st.dataframe(
            seg_counts.rename(columns={"rfm_segment": "Сегмент", "count": "Студентов"}),
            hide_index=True, use_container_width=True,
        )

    st.divider()

    # ── RFM scatter ───────────────────────────────────────────────────────────
    st.subheader("R vs F (цвет = сегмент)")
    fig = px.scatter(
        rfm_df,
        x="recency_days", y="session_count",
        color="rfm_segment",
        color_discrete_map=SEGMENT_COLORS,
        size="monetary",
        hover_data=["user_id", "monetary", "avg_score_pct"],
        title="Recency vs Frequency (размер = Educational Value)",
        labels={"recency_days": "Дней с последнего входа", "session_count": "Сессий"},
        opacity=0.7,
    )
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    col3, col4 = st.columns(2)
    with col3:
        st.subheader("F vs M")
        fig = px.scatter(
            rfm_df,
            x="session_count", y="monetary",
            color="rfm_segment",
            color_discrete_map=SEGMENT_COLORS,
            title="Frequency vs Educational Value",
            labels={"session_count": "Сессии", "monetary": "Educational Value"},
            opacity=0.7,
        )
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    with col4:
        st.subheader("Распределение RFM Score")
        rfm_df["rfm_score"] = rfm_df["r_score"] + rfm_df["f_score"] + rfm_df["m_score"]
        score_dist = rfm_df["rfm_score"].value_counts().reset_index()
        score_dist.columns = ["rfm_score", "count"]
        fig = bar_chart(score_dist.sort_values("rfm_score"), "rfm_score", "count",
                        title="Распределение суммарного RFM-балла (3–9)")
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    st.divider()

    # ── Segment detail tables ─────────────────────────────────────────────────
    st.subheader("Детализация по сегментам")
    selected_seg = st.selectbox(
        "Выберите сегмент",
        options=sorted(rfm_df["rfm_segment"].unique()),
        key="rfm_seg_select",
    )
    seg_detail = rfm_df[rfm_df["rfm_segment"] == selected_seg][
        ["user_id", "recency_days", "session_count", "event_count",
         "avg_duration_min", "monetary", "avg_score_pct", "att_pct"]
    ].sort_values("monetary", ascending=False).head(100)
    seg_detail.columns = [
        "User ID", "Дней с посл. входа", "Сессии", "События",
        "Ср. длит. (мин)", "Educational Value", "Ср. балл (%)", "Посещ. (%)",
    ]
    st.dataframe(seg_detail, use_container_width=True, hide_index=True)
