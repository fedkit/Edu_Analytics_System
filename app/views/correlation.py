"""Страница: Корреляция обучения — аналитика зависимостей поведения и успеваемости."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from clickhouse_connect.driver.client import Client
from plotly.subplots import make_subplots
from sqlalchemy.engine import Engine

from app.core.filters import FilterState
from app.services.correlation_service import CORR_LABELS, CorrelationService

# ── Цвета ─────────────────────────────────────────────────────────────────────
C_GOOD    = "#4CAF50"
C_NORMAL  = "#2196F3"
C_RISK    = "#FF9800"
C_CRITICAL= "#F44336"
C_NEUTRAL = "#78909C"
C_SPEARMAN = "#AB47BC"

ZONE_COLORS = {
    "Хорошо":   C_GOOD,
    "Нормально":C_NORMAL,
    "Риск":     C_RISK,
    "Критично": C_CRITICAL,
}

SEGMENT_COLORS = {
    "Активные отличники":     C_GOOD,
    "Активные, но отстают":   C_RISK,
    "Пассивные, но успевают": C_NORMAL,
    "Пассивные и отстают":    C_CRITICAL,
}


def _empty(msg: str = "Нет данных за выбранный период") -> None:
    st.info(msg)


def _scope(f: FilterState) -> str:
    if f.analysis_level == "group"   and f.group_name:   return f"Группа {f.group_name}"
    if f.analysis_level == "faculty" and f.faculty_name: return f.faculty_name
    return "Все участники"


# ── 1. Временной обзор ────────────────────────────────────────────────────────

def _render_overview(svc: CorrelationService, f: FilterState) -> None:
    st.markdown("## 1. Активность и успеваемость: совместная динамика")
    st.caption(
        "Обе метрики нормализованы к 0–100 для визуального сравнения. "
        "**Синхронный рост** — активность платформы связана с успеваемостью. "
        "**Расхождение** — активность растёт, а успеваемость нет (возможен пассивный просмотр)."
    )

    with st.spinner("Загрузка временных рядов..."):
        dual = svc.dual_timeseries(
            f.date_from, f.date_to, rolling=f.rolling_window,
            group_id=f.group_id, faculty_id=f.faculty_id,
        )

    if dual.empty:
        return _empty()

    w = f.rolling_window
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    gc = f"gpa_norm_ma{w}"
    sc = f"sessions_norm_ma{w}"

    if gc in dual.columns:
        fig.add_trace(go.Scatter(
            x=dual["date"], y=dual[gc],
            name="Успеваемость (норм.)", mode="lines",
            line=dict(color=C_NORMAL, width=2.5),
            hovertemplate="Дата: %{x|%d.%m.%Y}<br>Успеваемость: %{y:.1f}<extra></extra>",
        ), secondary_y=False)

    if sc in dual.columns:
        fig.add_trace(go.Scatter(
            x=dual["date"], y=dual[sc],
            name="Активность (норм.)", mode="lines",
            line=dict(color=C_RISK, width=2.5),
            hovertemplate="Дата: %{x|%d.%m.%Y}<br>Активность: %{y:.1f}<extra></extra>",
        ), secondary_y=True)

    fig.update_layout(
        hovermode="x unified", height=360,
        legend=dict(orientation="h", y=1.05),
    )
    fig.update_yaxes(title_text="Успеваемость (норм.)", secondary_y=False, range=[0, 115])
    fig.update_yaxes(title_text="Активность (норм.)",   secondary_y=True,  range=[0, 115])
    fig.update_xaxes(title_text="Дата")
    st.plotly_chart(fig, use_container_width=True)


# ── 2. Матрица корреляций ─────────────────────────────────────────────────────

def _render_corr_matrix(per_user_df: pd.DataFrame, method: str) -> None:
    st.markdown("## 2. Матрица корреляций: поведение vs успеваемость")
    st.caption(
        "Тепловая карта попарных корреляций. "
        "**Синий/зелёный** — положительная связь, **красный** — обратная, **нейтральный** — отсутствие. "
        "Под ячейкой — сила связи: |r|>0.5 значимо, |r|<0.2 слабо."
    )

    from app.services.correlation_service import BEHAVIOR_COLS, ACADEMIC_COLS
    cols = [c for c in BEHAVIOR_COLS + ACADEMIC_COLS if c in per_user_df.columns]
    if len(cols) < 3:
        return _empty("Недостаточно метрик для построения матрицы")

    sub = per_user_df[cols].apply(pd.to_numeric, errors="coerce")
    mat = sub.corr(method=method).round(3)

    labels = [CORR_LABELS.get(c, c) for c in mat.columns]
    z      = mat.values

    fig = go.Figure(go.Heatmap(
        z=z,
        x=labels,
        y=labels,
        colorscale=[
            [0.0,  "#B71C1C"],
            [0.35, "#EF9A9A"],
            [0.5,  "#ECEFF1"],
            [0.65, "#A5D6A7"],
            [1.0,  "#1B5E20"],
        ],
        zmid=0,
        zmin=-1, zmax=1,
        text=[[f"{v:.2f}" for v in row] for row in z],
        texttemplate="%{text}",
        textfont=dict(size=10),
        hovertemplate="<b>%{x}</b> ↔ <b>%{y}</b><br>r = %{z:.3f}<extra></extra>",
    ))
    fig.update_layout(
        height=max(400, len(cols) * 40),
        xaxis=dict(tickangle=-40),
        margin=dict(l=160, b=160),
    )
    st.plotly_chart(fig, use_container_width=True)

    pairs = []
    for i, c1 in enumerate(mat.columns):
        for j, c2 in enumerate(mat.columns):
            if j <= i:
                continue
            r = mat.iloc[i, j]
            if abs(r) >= 0.3:
                pairs.append((abs(r), r, CORR_LABELS.get(c1, c1), CORR_LABELS.get(c2, c2)))
    if pairs:
        pairs.sort(reverse=True)
        st.markdown("**Сильнейшие связи (|r| ≥ 0.3):**")
        for _, r, a, b in pairs[:5]:
            direction = "положительная" if r > 0 else "обратная"
            st.markdown(f"- **{a}** ↔ **{b}**: r = {r:+.3f} ({direction})")


# ── 3. Lag-анализ (недельный) ─────────────────────────────────────────────────

def _render_lag(svc: CorrelationService, f: FilterState) -> None:
    st.markdown("## 3. Lag-анализ: отложенный эффект активности")
    st.caption(
        "Показывает, **через сколько недель** активность в системе предсказывает рост успеваемости. "
        "**Сдвиг 0** — мгновенная связь, **сдвиг 2** — эффект через 2 недели. "
        "Максимум при сдвиге > 0 означает, что активность **опережает** успеваемость. "
        "Отображаются оба метода — Пирсон и Спирмен."
    )

    c1, c2 = st.columns(2)
    pred_opts = {
        "sessions":     "Сессии",
        "dau":          "ДАП",
        "avg_duration": "Длит. сессии",
        "events":       "События",
    }
    tgt_opts = {
        "progress":   "Успеваемость (score %)",
        "pass_rate":  "Доля сдавших",
        "attendance": "Посещаемость",
    }
    predictor = c1.selectbox("Предиктор (активность)", list(pred_opts.keys()), format_func=lambda k: pred_opts[k])
    target    = c2.selectbox("Цель (успеваемость)",    list(tgt_opts.keys()),  format_func=lambda k: tgt_opts[k])

    kw = dict(
        start=f.date_from, end=f.date_to,
        predictor=predictor, target=target,
        group_id=f.group_id, faculty_id=f.faculty_id,
    )
    with st.spinner("Lag-анализ..."):
        lag_pearson  = svc.lag_analysis_weekly(**kw, method="pearson")
        lag_spearman = svc.lag_analysis_weekly(**kw, method="spearman")

    if lag_pearson.empty:
        return _empty("Недостаточно недельных данных для lag-анализа")

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=lag_pearson["lag_label"],
        y=lag_pearson["correlation"],
        name="Пирсон",
        marker_color=C_NORMAL,
        text=[f"{v:+.3f}" if not np.isnan(v) else "н/д" for v in lag_pearson["correlation"]],
        textposition="outside",
        hovertemplate="Сдвиг: %{x}<br>Пирсон r = %{y:.3f}<extra></extra>",
        offsetgroup=0,
    ))

    if not lag_spearman.empty:
        fig.add_trace(go.Bar(
            x=lag_spearman["lag_label"],
            y=lag_spearman["correlation"],
            name="Спирмен",
            marker_color=C_SPEARMAN,
            text=[f"{v:+.3f}" if not np.isnan(v) else "н/д" for v in lag_spearman["correlation"]],
            textposition="outside",
            hovertemplate="Сдвиг: %{x}<br>Спирмен ρ = %{y:.3f}<extra></extra>",
            offsetgroup=1,
        ))

    fig.add_hline(y=0,    line_dash="dash", line_color="#888")
    fig.add_hline(y=0.3,  line_dash="dot",  line_color=C_GOOD,     opacity=0.5)
    fig.add_hline(y=-0.3, line_dash="dot",  line_color=C_CRITICAL, opacity=0.5)
    fig.update_layout(
        barmode="group",
        xaxis_title="Сдвиг", yaxis_title="Корреляция",
        yaxis=dict(range=[-1.1, 1.1]), height=380,
        legend=dict(orientation="h", y=1.05),
    )
    st.plotly_chart(fig, use_container_width=True)

    valid = lag_pearson.dropna(subset=["correlation"])
    if not valid.empty:
        best = valid.loc[valid["correlation"].abs().idxmax()]
        r, lbl = best["correlation"], best["lag_label"]
        if abs(r) > 0.15:
            direction = "положительная" if r > 0 else "обратная"
            st.success(
                f"Наибольшая {direction} корреляция Пирсона (r = {r:+.3f}) при сдвиге **{lbl}**. "
                f"Это означает, что *{pred_opts[predictor]}* "
                f"опережает *{tgt_opts[target]}* примерно на этот срок."
            )


# ── 4. Скользящие корреляции ─────────────────────────────────────────────────

def _render_rolling(svc: CorrelationService, f: FilterState) -> None:
    st.markdown("## 4. Эволюция корреляций во времени")
    st.caption(
        f"Скользящая корреляция (окно {f.rolling_window} дней). "
        "**Усиление к сессии** — нормальная картина. "
        "**Обвал корреляции** — поведение отвязалось от учёбы (каникулы, кризис). "
        "Сплошные линии — Пирсон, пунктир — Спирмен."
    )

    with st.spinner("Вычисление скользящих корреляций..."):
        corr = svc.rolling_correlations(
            f.date_from, f.date_to,
            window=f.rolling_window,
            group_id=f.group_id, faculty_id=f.faculty_id,
        )

    if corr.empty:
        return _empty(f"Недостаточно данных для окна {f.rolling_window} дней")

    fig = go.Figure()
    pairs = [
        ("corr_gpa_sessions",  "scorr_gpa_sessions",  "СОУ ↔ Сессии",        C_NORMAL),
        ("corr_gpa_dau",       "scorr_gpa_dau",        "СОУ ↔ ДАП",           "#0288D1"),
        ("corr_att_sessions",  "scorr_att_sessions",   "Посещаемость ↔ Сессии", C_GOOD),
        ("corr_gpa_duration",  "scorr_gpa_duration",   "СОУ ↔ Длит. сессий",  "#7B1FA2"),
    ]
    for pcol, scol, label, color in pairs:
        if pcol in corr.columns:
            fig.add_trace(go.Scatter(
                x=corr["date"], y=corr[pcol],
                name=f"{label} (Пирсон)", mode="lines",
                line=dict(color=color, width=2),
                hovertemplate=f"{label} Пирсон: %{{y:.3f}}<extra></extra>",
            ))
        if scol in corr.columns:
            fig.add_trace(go.Scatter(
                x=corr["date"], y=corr[scol],
                name=f"{label} (Спирмен)", mode="lines",
                line=dict(color=color, width=1.5, dash="dot"),
                opacity=0.7,
                hovertemplate=f"{label} Спирмен: %{{y:.3f}}<extra></extra>",
            ))

    fig.add_hline(y=0,    line_dash="dash", line_color="#888", line_width=1.5)
    fig.add_hline(y=0.3,  line_dash="dot",  line_color=C_GOOD,     opacity=0.4)
    fig.add_hline(y=-0.3, line_dash="dot",  line_color=C_CRITICAL, opacity=0.4)
    fig.update_layout(
        xaxis_title="Дата", yaxis_title="Корреляция",
        yaxis=dict(range=[-1.05, 1.05]),
        hovermode="x unified", legend=dict(orientation="h", y=1.05), height=420,
    )
    st.plotly_chart(fig, use_container_width=True)

    if "coupling_index_ma7" in corr.columns:
        fig2 = go.Figure(go.Scatter(
            x=corr["date"], y=corr["coupling_index_ma7"],
            mode="lines", fill="tozeroy",
            line=dict(color="#6A1B9A", width=2.5),
            fillcolor="rgba(106,27,154,0.08)",
            hovertemplate="Дата: %{x|%d.%m.%Y}<br>Сопряжённость: %{y:.3f}<extra></extra>",
        ))
        fig2.add_hrect(y0=0.4, y1=1.0, fillcolor="rgba(76,175,80,0.05)", line_width=0,
                       annotation_text="Высокая сопряжённость", annotation_position="right")
        fig2.update_layout(
            title="Индекс сопряжённости (среднее |r| всех пар)",
            xaxis_title="Дата", yaxis_title="|r| среднее",
            yaxis=dict(range=[0, 1.1]), height=280, showlegend=False,
        )
        st.plotly_chart(fig2, use_container_width=True)


# ── 5. Поведенческая сегментация ─────────────────────────────────────────────

def _render_segments(svc: CorrelationService, per_user_df: pd.DataFrame) -> None:
    st.markdown("## 5. Поведенческая сегментация студентов")
    st.caption("Кластеризация по метрикам активности и успеваемости.")

    with st.spinner("Кластеризация..."):
        seg_df = svc.behavioral_segments(per_user_df)

    if seg_df.empty:
        return _empty("Недостаточно данных для кластеризации (нужно ≥ 12 студентов)")

    numeric_cols = [c for c in ["sessions_per_week", "avg_duration_min", "active_days",
                                 "progress_pct", "att_pct"] if c in seg_df.columns]
    if numeric_cols:
        stats_df = seg_df.groupby("segment")[numeric_cols].mean().round(1).reset_index()
        stats_df.columns = ["Сегмент"] + [
            {"sessions_per_week": "Сессий/нед", "avg_duration_min": "Длит.(мин)",
             "active_days": "Акт.дней", "progress_pct": "Прогресс%",
             "att_pct": "Посещ.%"}.get(c, c)
            for c in numeric_cols
        ]
        st.dataframe(stats_df, hide_index=True, use_container_width=True)
    else:
        _empty("Нет числовых метрик для отображения")


# ── 6. Ранняя сигнализация ────────────────────────────────────────────────────

def _render_early_warning(svc: CorrelationService, f: FilterState) -> None:
    st.markdown("## 6. Ранняя сигнализация: студенты в зоне риска")
    st.caption(
        "Студенты, у которых **активность снижается** (отрицательный тренд сессий) "
        "и **прогресс ниже 70%**. Таким студентам нужна поддержка сейчас, "
        "чтобы не перейти в критическую зону."
    )

    with st.spinner("Анализ трендов..."):
        warn_df = svc.early_warning(
            f.date_from, f.date_to,
            group_id=f.group_id, faculty_id=f.faculty_id,
        )

    if warn_df.empty:
        st.success("Студентов с одновременно снижающейся активностью и низким прогрессом не обнаружено.")
        return

    st.warning(f"Обнаружено **{len(warn_df)}** студентов с признаками риска:")

    display = warn_df.rename(columns={
        "name":                  "Студент",
        "current_progress":      "Прогресс %",
        "sessions_trend":        "Тренд сессий",
        "last_week_sessions":    "Сессий (последняя нед.)",
        "weeks_tracked":         "Недель в данных",
    })
    cols = [c for c in ["Студент", "Прогресс %", "Тренд сессий",
                         "Сессий (последняя нед.)", "Недель в данных"] if c in display.columns]
    st.dataframe(display[cols], hide_index=True, use_container_width=True)


# ── Главная функция ───────────────────────────────────────────────────────────

def render(filters: FilterState, engine: Engine, ch: Client) -> None:
    svc = CorrelationService(engine, ch)

    st.title("Корреляция обучения и активности")
    scope = _scope(filters)
    method_label = "Пирсон" if filters.corr_method == "pearson" else "Спирмен"
    st.caption(
        f"Период: **{filters.date_from.strftime('%d.%m.%Y')} — "
        f"{filters.date_to.strftime('%d.%m.%Y')}** "
        f"· Уровень: **{scope}** "
        f"· Метод матрицы: **{method_label}** "
        f"· Окно скользящей: **{filters.rolling_window} дней**"
    )

    with st.spinner("Загрузка данных студентов..."):
        per_user_df = svc.combined_per_user(
            filters.date_from, filters.date_to,
            group_id=filters.group_id,
            faculty_id=filters.faculty_id,
        )

    has_per_user = not per_user_df.empty
    if has_per_user:
        n_students = per_user_df["user_id"].nunique()
        st.caption(f"В анализе: **{n_students}** студентов с данными в обеих системах.")
    else:
        st.warning(
            "Нет данных о студентах в обеих системах (система + академическая). "
            "Часть блоков будет недоступна."
        )

    _render_overview(svc, filters)
    st.divider()

    if has_per_user:
        _render_corr_matrix(per_user_df, filters.corr_method)
        st.divider()

    _render_lag(svc, filters)
    st.divider()

    _render_rolling(svc, filters)
    st.divider()

    if has_per_user:
        _render_segments(svc, per_user_df)
        st.divider()

    _render_early_warning(svc, filters)
