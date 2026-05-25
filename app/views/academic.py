"""Страница: Академическая аналитика — накопительный прогресс."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy.engine import Engine

from app.core.filters import FilterState
from app.core.time_aggregation import add_rolling_avg
from app.queries import postgres_queries as pq
from app.services.academic_service import (
    build_academic_kpis,
    calculate_attendance_vs_progress,
    calculate_cumulative_scores,
    calculate_risk_share,
    calculate_student_distribution,
    calculate_weekly_velocity,
    load_academic_data,
    status_color,
    status_label,
)

C_SCORE    = "#2196F3"
C_MAX      = "#90CAF9"
C_PROGRESS = "#4CAF50"
C_RISK     = "#F44336"
C_ATT      = "#26C6DA"
C_VELOCITY = "#FF9800"
C_MIN      = "#888888"


def _empty(msg: str = "Нет данных за выбранный период") -> None:
    st.info(msg)


def _scope_label(f: FilterState) -> str:
    if f.analysis_level == "student" and f.student_name:
        return f.student_name
    if f.analysis_level == "group" and f.group_name:
        return f"Группа {f.group_name}"
    if f.analysis_level == "faculty" and f.faculty_name:
        return f.faculty_name
    return "Все участники"


# ── KPI-карточки ──────────────────────────────────────────────────────────────

def render_kpis(kpis: dict) -> None:
    cols = st.columns(7)
    items = [
        ("Накоплено баллов",          kpis.get("cum_score"),          "{:.1f}",  ""),
        ("Прогресс",                  kpis.get("overall_progress"),   "{:.1f}%", ""),
        ("Макс. на дату",             kpis.get("cum_max"),            "{:.1f}",  ""),
        ("Зона риска",                kpis.get("risk_share"),         "{:.1f}%", ""),
        ("Pass rate",                 kpis.get("pass_rate"),          "{:.1f}%", ""),
        ("Посещаемость",              kpis.get("avg_attendance"),     "{:.1f}%", ""),
        ("Темп (баллов/нед.)",        kpis.get("avg_weekly_velocity"),"{:.1f}",  ""),
    ]
    for col, (label, val, fmt, _) in zip(cols, items):
        if val is not None and not (isinstance(val, float) and pd.isna(val)):
            col.metric(label, fmt.format(val))
        else:
            col.metric(label, "—")


# ── 1. Накопленный балл по времени ────────────────────────────────────────────

def render_cumulative_chart(cum_df: pd.DataFrame, rolling: int) -> None:
    st.markdown("## 1. Накопленный балл по времени")
    st.caption(
        "Линия «Набрано» — фактически накопленные баллы. "
        "«Доступно» — максимум по уже выставленным работам. "
        "«Минимум» — 60% от доступного. "
        "**Плохой сигнал:** синяя линия ниже серой."
    )

    if cum_df.empty:
        return _empty()

    ma_col = f"cum_score_ma{rolling}"
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=cum_df["date"], y=cum_df["cum_max"],
        name="Доступно (макс.)", mode="lines",
        line=dict(color=C_MAX, width=2, dash="dash"),
        hovertemplate="Дата: %{x|%d.%m.%Y}<br>Доступно: %{y:.1f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=cum_df["date"], y=cum_df["min_expected"],
        name="Минимум (60%)", mode="lines",
        line=dict(color=C_MIN, width=1.5, dash="dot"),
        hovertemplate="Минимум 60%%: %{y:.1f}<extra></extra>",
    ))
    y_score = cum_df[ma_col] if ma_col in cum_df.columns else cum_df["cum_score"]
    fig.add_trace(go.Scatter(
        x=cum_df["date"], y=y_score,
        name="Набрано (факт)", mode="lines",
        line=dict(color=C_SCORE, width=2.5),
        fill="tozeroy", fillcolor="rgba(33,150,243,0.08)",
        hovertemplate="Дата: %{x|%d.%m.%Y}<br>Набрано: %{y:.1f}<extra></extra>",
    ))
    fig.update_layout(
        xaxis_title="Дата", yaxis_title="Накопленные баллы",
        hovermode="x unified", height=380,
        legend=dict(orientation="h", y=1.05),
    )
    st.plotly_chart(fig, use_container_width=True)


# ── 2. Прогресс относительно доступного максимума ────────────────────────────

def render_progress_chart(cum_df: pd.DataFrame, rolling: int) -> None:
    st.markdown("## 2. Прогресс относительно доступного максимума")
    st.caption(
        "Набрано / Доступно × 100%. Показывает, насколько полно закрываются уже "
        "выставленные задания. **Красная зона (< 40%)** — критическое отставание."
    )

    if cum_df.empty:
        return _empty()

    ma_col = f"progress_pct_ma{rolling}"
    y = cum_df[ma_col] if ma_col in cum_df.columns else cum_df["progress_pct"]
    fig = go.Figure()

    for y0, y1, color, label in [
        (0,  40,  "rgba(244,67,54,0.08)",   "Критично"),
        (40, 60,  "rgba(255,152,0,0.08)",   "Риск"),
        (60, 80,  "rgba(33,150,243,0.06)",  "Нормально"),
        (80, 100, "rgba(76,175,80,0.08)",   "Хорошо"),
    ]:
        fig.add_hrect(y0=y0, y1=y1, fillcolor=color, line_width=0,
                      annotation_text=label, annotation_position="right",
                      annotation=dict(font_size=10))

    fig.add_trace(go.Scatter(
        x=cum_df["date"], y=cum_df["progress_pct"],
        name="Прогресс (сырой)", mode="lines",
        line=dict(color=C_PROGRESS, width=1, dash="dot"), opacity=0.3, showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=cum_df["date"], y=y,
        name=f"Прогресс MA{rolling}", mode="lines",
        line=dict(color=C_PROGRESS, width=2.5),
        hovertemplate="Дата: %{x|%d.%m.%Y}<br>Прогресс: %{y:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        xaxis_title="Дата", yaxis_title="Прогресс (%)",
        yaxis=dict(range=[0, 105]),
        hovermode="x unified", height=380,
    )
    st.plotly_chart(fig, use_container_width=True)


# ── 3. Темп набора баллов по неделям ─────────────────────────────────────────

def render_velocity_chart(velocity_df: pd.DataFrame) -> None:
    st.markdown("## 3. Темп набора баллов по неделям")
    st.caption(
        "Средний прирост баллов на студента за каждую неделю. "
        "**Серые столбцы** — недели без новых оценок (возможно, каникулы или пробел в данных)."
    )

    if velocity_df.empty:
        return _empty()

    colors = [
        "rgba(128,128,128,0.5)" if z else "rgba(255,152,0,0.8)"
        for z in velocity_df["is_zero"]
    ]
    fig = go.Figure(go.Bar(
        x=velocity_df["week"], y=velocity_df["avg_weekly_score"],
        marker_color=colors,
        hovertemplate="Неделя: %{x|%d.%m.%Y}<br>Баллов/студент: %{y:.2f}<extra></extra>",
    ))
    fig.update_layout(
        xaxis_title="Неделя", yaxis_title="Баллов на студента",
        hovermode="x unified", height=340,
    )
    st.plotly_chart(fig, use_container_width=True)


# ── 4. Доля студентов в зоне риска ───────────────────────────────────────────

def render_risk_chart(risk_df: pd.DataFrame) -> None:
    st.markdown("## 4. Доля студентов в зоне риска")
    st.caption(
        "Процент студентов, у которых накопленный прогресс ниже 60% от доступного максимума. "
        "**Рост линии** — тревожный сигнал: всё больше студентов отстают."
    )

    if risk_df.empty:
        return _empty("Недостаточно данных для расчёта зоны риска (нужно ≥ 2 студентов)")

    fig = go.Figure()
    fig.add_hline(y=30, line_dash="dash", line_color=C_RISK, line_width=1,
                  annotation_text="30% — порог тревоги", annotation_position="bottom right",
                  annotation=dict(font_color=C_RISK, font_size=10))
    fig.add_trace(go.Scatter(
        x=risk_df["week"], y=risk_df["risk_pct"],
        name="Зона риска", mode="lines+markers",
        line=dict(color=C_RISK, width=2.5),
        fill="tozeroy", fillcolor="rgba(244,67,54,0.07)",
        hovertemplate="Неделя: %{x|%d.%m.%Y}<br>В зоне риска: %{y:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        xaxis_title="Неделя", yaxis_title="Доля студентов (%)",
        yaxis=dict(range=[0, 105]),
        hovermode="x unified", height=340,
    )
    st.plotly_chart(fig, use_container_width=True)


# ── 5. Распределение прогресса ────────────────────────────────────────────────

def render_distribution_chart(dist_df: pd.DataFrame, level: str) -> None:
    st.markdown("## 5. Распределение прогресса")
    if level == "student":
        st.caption("Прогресс по каждому предмету студента (набрано / доступно × 100%).")
    else:
        st.caption(
            "Распределение прогресса по студентам. "
            "Histogram показывает, сколько студентов в каждой зоне. "
            "**Смещение влево** — много отстающих."
        )

    if dist_df.empty or "progress_pct" not in dist_df.columns:
        return _empty()

    fig = go.Figure(go.Histogram(
        x=dist_df["progress_pct"],
        nbinsx=20,
        marker_color=C_SCORE,
        opacity=0.8,
        hovertemplate="Прогресс: %{x:.0f}%<br>Кол-во: %{y}<extra></extra>",
    ))
    for x, color, label in [
        (40, C_RISK,     "40% — критично"),
        (60, C_VELOCITY, "60% — риск"),
        (80, C_PROGRESS, "80% — хорошо"),
    ]:
        fig.add_vline(x=x, line_dash="dash", line_color=color, line_width=1,
                      annotation_text=label, annotation_position="top right",
                      annotation=dict(font_size=10, font_color=color))
    fig.update_layout(
        xaxis_title="Прогресс (%)", yaxis_title="Количество",
        xaxis=dict(range=[0, 105]),
        height=340,
    )
    st.plotly_chart(fig, use_container_width=True)


# ── 6. Посещаемость vs Успеваемость ──────────────────────────────────────────

def render_scatter_chart(scatter_df: pd.DataFrame, level: str) -> None:
    st.markdown("## 6. Посещаемость vs Успеваемость")
    x_label = "Предмет" if level == "student" else "Студент"
    st.caption(
        f"Каждая точка — {x_label.lower()}. "
        "Ось X — посещаемость (%), ось Y — прогресс (%). "
        "**Идеально:** точки в правом верхнем углу. "
        "Точки слева внизу — проблемные случаи."
    )

    if scatter_df.empty or "att_pct" not in scatter_df.columns:
        return _empty()

    valid = scatter_df.dropna(subset=["att_pct", "progress_pct"])
    if valid.empty:
        return _empty()

    colors = [status_color(status_label(p)) for p in valid["progress_pct"]]
    fig = go.Figure(go.Scatter(
        x=valid["att_pct"],
        y=valid["progress_pct"],
        mode="markers",
        text=valid.get("label", valid.index.astype(str)),
        marker=dict(size=9, color=colors, opacity=0.75,
                    line=dict(color="white", width=0.5)),
        hovertemplate=(
            "%{text}<br>"
            "Посещаемость: %{x:.1f}%<br>"
            "Прогресс: %{y:.1f}%<extra></extra>"
        ),
    ))
    fig.add_hline(y=60, line_dash="dash", line_color=C_MIN, line_width=1)
    fig.add_vline(x=75, line_dash="dash", line_color=C_MIN, line_width=1)
    fig.update_layout(
        xaxis_title="Посещаемость (%)", yaxis_title="Прогресс (%)",
        xaxis=dict(range=[0, 105]), yaxis=dict(range=[0, 105]),
        height=420,
    )
    st.plotly_chart(fig, use_container_width=True)


# ── 7. Таблица проблемных объектов ───────────────────────────────────────────

def render_summary_table(engine: Engine, f: FilterState) -> None:
    st.markdown("## 7. Сводная таблица")

    level = f.analysis_level

    if level == "student" and f.student_id:
        df = pq.summary_table_student(engine, f.student_id, f.date_from, f.date_to)
        if df.empty:
            return _empty()
        df["Статус"] = df["progress_pct"].apply(status_label)
        df = df.rename(columns={
            "subject_name": "Предмет",
            "scored":       "Набрано",
            "available":    "Доступно",
            "progress_pct": "Прогресс %",
            "att_pct":      "Посещаемость %",
        })
        cols = ["Предмет", "Набрано", "Доступно", "Прогресс %", "Посещаемость %", "Статус"]

    elif level == "group" and f.group_id:
        df = pq.summary_table_group(engine, f.group_id, f.date_from, f.date_to)
        if df.empty:
            return _empty()
        df["Статус"] = df["progress_pct"].apply(status_label)
        df = df.rename(columns={
            "student_name": "Студент",
            "progress_pct": "Прогресс %",
            "att_pct":      "Посещаемость %",
            "pass_rate":    "Pass rate %",
        })
        cols = ["Студент", "Прогресс %", "Посещаемость %", "Pass rate %", "Статус"]

    elif level == "faculty" and f.faculty_id:
        df = pq.summary_table_faculty(engine, f.faculty_id, f.date_from, f.date_to)
        if df.empty:
            return _empty()
        df["Статус"] = df["avg_progress"].apply(status_label)
        df = df.rename(columns={
            "group_name":   "Группа",
            "avg_progress": "Ср. прогресс %",
            "avg_att":      "Посещаемость %",
            "pass_rate":    "Pass rate %",
            "risk_share":   "Зона риска %",
        })
        cols = ["Группа", "Ср. прогресс %", "Посещаемость %", "Pass rate %", "Зона риска %", "Статус"]

    else:
        df = pq.summary_table_all(engine, f.date_from, f.date_to)
        if df.empty:
            return _empty()
        df["Статус"] = df["avg_progress"].apply(status_label)
        df = df.rename(columns={
            "faculty_name": "Факультет",
            "avg_progress": "Ср. прогресс %",
            "avg_att":      "Посещаемость %",
            "pass_rate":    "Pass rate %",
            "risk_share":   "Зона риска %",
        })
        cols = ["Факультет", "Ср. прогресс %", "Посещаемость %", "Pass rate %", "Зона риска %", "Статус"]

    existing_cols = [c for c in cols if c in df.columns]
    st.dataframe(df[existing_cols], use_container_width=True, hide_index=True)


# ── Главная функция рендера ───────────────────────────────────────────────────

def render(filters: FilterState, engine: Engine) -> None:
    st.title("Академическая аналитика")
    scope = _scope_label(filters)
    st.caption(
        f"Период: **{filters.date_from.strftime('%d.%m.%Y')} — "
        f"{filters.date_to.strftime('%d.%m.%Y')}** · Уровень: **{scope}**"
        + (f" · Предмет: {filters.subject_name}" if filters.subject_name else "")
        + (f" · Семестр {filters.semester_filter}" if filters.semester_filter else "")
        + (f" · {filters.course_filter} курс" if filters.course_filter else "")
    )

    # Если student выбран, но конкретный студент не указан — предупреждение
    if filters.analysis_level == "student" and not filters.student_id:
        st.warning("Выберите студента в боковой панели (введите фамилию или никнейм).")
        return

    with st.spinner("Загрузка данных..."):
        scores_df, attendance_df = load_academic_data(
            engine,
            filters.date_from, filters.date_to,
            student_id=filters.student_id,
            group_id=filters.group_id,
            faculty_id=filters.faculty_id,
            subject_id=filters.subject_id,
            semester=filters.semester_filter,
            course=filters.course_filter,
        )

    if scores_df.empty:
        st.warning("Нет данных по оценкам для выбранных фильтров.")
        return

    # Вычисляем все метрики
    cum_df      = calculate_cumulative_scores(scores_df, rolling=filters.rolling_window)
    velocity_df = calculate_weekly_velocity(scores_df)
    risk_df     = calculate_risk_share(scores_df)
    dist_df     = calculate_student_distribution(scores_df)

    # Для scatter нужны названия предметов
    subj_names = None
    if filters.analysis_level == "student":
        try:
            subj_names = pq.subject_names(engine)
        except Exception:
            pass

    scatter_df = calculate_attendance_vs_progress(
        scores_df, attendance_df,
        level=filters.analysis_level,
        subject_names_df=subj_names,
    )

    kpis = build_academic_kpis(cum_df, scores_df, attendance_df, risk_df, velocity_df)

    # ── KPI ──────────────────────────────────────────────────────────────────
    render_kpis(kpis)
    st.divider()

    # ── Графики ──────────────────────────────────────────────────────────────
    render_cumulative_chart(cum_df, filters.rolling_window)
    st.divider()

    render_progress_chart(cum_df, filters.rolling_window)
    st.divider()

    render_velocity_chart(velocity_df)
    st.divider()

    # Риск только если несколько студентов
    if filters.analysis_level != "student":
        render_risk_chart(risk_df)
        st.divider()

    render_distribution_chart(dist_df, filters.analysis_level)
    st.divider()

    render_scatter_chart(scatter_df, filters.analysis_level)
    st.divider()

    render_summary_table(engine, filters)
