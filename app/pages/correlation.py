"""Correlation Analytics — behavior vs academic performance."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components.charts import (
    PLOTLY_CONFIG, correlation_matrix_chart, line_chart, scatter_chart,
)
from app.components.filters import FilterState
from app.repositories.academic_repo import AcademicRepository
from app.repositories.behavior_repo import BehaviorRepository
from app.services.correlation_service import (
    build_correlation_matrix, compute_correlation, generate_insight,
)


METRIC_LABELS = {
    "session_count":     "Кол-во сессий",
    "event_count":       "Кол-во событий",
    "avg_duration_min":  "Ср. длит. сессии (мин)",
    "unique_pages":      "Уникальных страниц",
    "course_views":      "Просмотры курсов",
    "exam_views":        "Просмотры экзаменов",
    "avg_score_pct":     "Средний балл (%)",
    "att_pct":           "Посещаемость (%)",
}


def render(
    f: FilterState,
    behavior: BehaviorRepository,
    academic: AcademicRepository,
) -> None:
    st.title("🔗 Корреляционный анализ")
    st.caption(f"Период: {f.start_date} — {f.end_date}")
    st.info(
        "Анализ взаимосвязи между поведением на платформе "
        "и академической успеваемостью студентов."
    )

    with st.spinner("Загрузка данных…"):
        beh_df  = behavior.get_per_user_behavior(f.start_date, f.end_date)
        acad_df = academic.get_per_user_academic_summary(f.start_date, f.end_date)

    if beh_df.empty or acad_df.empty:
        st.info("Недостаточно данных для корреляционного анализа.")
        return

    merged = beh_df.merge(acad_df, on="user_id", how="inner")

    if len(merged) < 20:
        st.warning(f"Слишком мало точек данных ({len(merged)}) — корреляции могут быть ненадёжны.")

    # ── Correlation selector ──────────────────────────────────────────────────
    st.subheader("Выбор метрик")
    col1, col2, col3 = st.columns(3)
    with col1:
        x_metric = st.selectbox(
            "Ось X (поведение)",
            [k for k in METRIC_LABELS if k not in ("avg_score_pct", "att_pct")],
            format_func=lambda k: METRIC_LABELS[k],
            key="corr_x",
        )
    with col2:
        y_metric = st.selectbox(
            "Ось Y (академика)",
            ["avg_score_pct", "att_pct"],
            format_func=lambda k: METRIC_LABELS[k],
            key="corr_y",
        )
    with col3:
        method = st.radio("Метод", ["pearson", "spearman"], horizontal=True, key="corr_method")

    # ── Compute & display correlation ─────────────────────────────────────────
    r, p = compute_correlation(merged[x_metric], merged[y_metric], method)

    col_r, col_p, col_n = st.columns(3)
    col_r.metric("Коэффициент корреляции (r)", f"{r:+.4f}")
    col_p.metric("p-value", f"{p:.4f}", delta="значим" if p < 0.05 else "незначим")
    col_n.metric("Наблюдений", f"{len(merged):,}")

    st.success(generate_insight(METRIC_LABELS[x_metric], METRIC_LABELS[y_metric], r))

    # ── Scatter chart ─────────────────────────────────────────────────────────
    fig = scatter_chart(
        merged, x=x_metric, y=y_metric,
        title=f"{METRIC_LABELS[x_metric]} vs {METRIC_LABELS[y_metric]}",
        trendline=True,
    )
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    st.divider()

    # ── Full correlation matrix ───────────────────────────────────────────────
    st.subheader("Матрица корреляций (все метрики)")
    corr_cols = [c for c in METRIC_LABELS if c in merged.columns]
    corr_matrix = build_correlation_matrix(merged, corr_cols)
    corr_matrix.index   = [METRIC_LABELS.get(c, c) for c in corr_matrix.index]
    corr_matrix.columns = [METRIC_LABELS.get(c, c) for c in corr_matrix.columns]
    fig = correlation_matrix_chart(corr_matrix)
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    st.divider()

    # ── Segment insights ──────────────────────────────────────────────────────
    st.subheader("Топ-5% по активности vs остальные")
    threshold = merged["session_count"].quantile(0.95)
    high  = merged[merged["session_count"] >= threshold]
    low   = merged[merged["session_count"] <  threshold]

    if not high.empty and not low.empty:
        gpa_high = high["avg_score_pct"].mean()
        gpa_low  = low["avg_score_pct"].mean()
        diff_pct = (gpa_high - gpa_low) / max(gpa_low, 0.01) * 100
        sign = "выше" if diff_pct > 0 else "ниже"
        st.info(
            f"Студенты из топ-5% по количеству сессий (≥ {threshold:.0f}) "
            f"имеют средний балл **{gpa_high:.1f}%**, "
            f"что **{abs(diff_pct):.1f}% {sign}**, чем у остальных ({gpa_low:.1f}%)."
        )

    col_a, col_b = st.columns(2)
    with col_a:
        buckets = pd.cut(merged["session_count"], bins=5).astype(str)
        merged["session_bucket"] = buckets
        bucket_agg = merged.groupby("session_bucket")["avg_score_pct"].mean().reset_index()
        fig = scatter_chart(bucket_agg, "session_bucket", "avg_score_pct",
                            title="Ср. балл по квантилям сессий", trendline=False)
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    with col_b:
        att_corr_r, att_corr_p = compute_correlation(
            merged["att_pct"], merged["avg_score_pct"], method
        )
        st.metric("Посещаемость ↔ Балл (r)", f"{att_corr_r:+.4f}")
        st.metric("p-value", f"{att_corr_p:.4f}")
        st.info(generate_insight("Посещаемость (%)", "Средний балл (%)", att_corr_r))
