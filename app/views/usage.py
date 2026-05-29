"""Страница 2: Аналитика использования сайта — поведенческие временны́е ряды."""
from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from clickhouse_connect.driver.client import Client
from plotly.subplots import make_subplots

from app.core.filters import FilterState
from app.core.time_aggregation import GRANULARITY_LABELS
from app.services.usage_service import UsageService

# ── Цветовая палитра ──────────────────────────────────────────────────────────
C_DAU      = "#1565C0"
C_WAU      = "#1976D2"
C_MAU      = "#42A5F5"
C_SESSIONS = "#E65100"
C_DURATION = "#2E7D32"
C_EVENTS   = "#6A1B9A"
C_INDEX    = "#00838F"
SECTION_COLORS = {
    "home":     "#1f77b4",
    "course":   "#ff7f0e",
    "exam":     "#d62728",
    "grades":   "#2ca02c",
    "schedule": "#9467bd",
    "library":  "#8c564b",
    "profile":  "#7f7f7f",
}
SECTION_LABELS = {
    "home":     "Главная",
    "course":   "Курсы",
    "exam":     "Экзамены",
    "grades":   "Оценки",
    "schedule": "Расписание",
    "library":  "Библиотека",
    "profile":  "Профиль",
}
DOW_LABELS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def _empty(msg: str = "Нет данных за выбранный период") -> None:
    st.info(msg)


def render(filters: FilterState, ch: Client) -> None:
    svc = UsageService(ch)

    st.title("Аналитика использования")
    st.caption(
        f"Период: **{filters.date_from.strftime('%d.%m.%Y')} — {filters.date_to.strftime('%d.%m.%Y')}** "
        f"· {GRANULARITY_LABELS[filters.granularity]} "
        f"· Сглаживание СС{filters.rolling_window}"
    )

    # ── 1. Единый индекс вовлечённости ────────────────────────────────────────
    st.markdown("## 1. Единый индекс вовлечённости")
    st.caption("Нормализованный составной показатель: ДАП + сессии + длительность + события.")
    with st.expander("Из чего состоит индекс?"):
        st.markdown(
            "Индекс вовлечённости — взвешенная сумма четырёх метрик, каждая из которых "
            "нормализована в диапазон **0–100** по всей выборке:\n\n"
            "| Метрика | Вес |\n"
            "|---|---|\n"
            "| Дневные активные пользователи (ДАП) | **30%** |\n"
            "| Число сессий | **25%** |\n"
            "| Средняя длительность сессии | **25%** |\n"
            "| Число событий (кликов/действий) | **20%** |\n\n"
            "Итоговое значение от **0** (нет активности) до **100** (максимум по периоду). "
            "Сравнивать абсолютные значения между разными периодами некорректно — "
            "нормировка выполняется внутри каждой выборки."
        )

    with st.spinner("Загрузка данных..."):
        eng = svc.engagement_timeseries(
            filters.date_from, filters.date_to,
            granularity=filters.granularity,
            rolling=filters.rolling_window,
        )

    if eng.empty:
        _empty()
    else:
        w = filters.rolling_window
        fig1 = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                             row_heights=[0.4, 0.6],
                             subplot_titles=("Индекс вовлечённости", "Составляющие: ДАП · Сессии · События"))

        if "engagement_index" in eng.columns:
            fig1.add_trace(go.Scatter(
                x=eng["date"], y=eng["engagement_index"],
                name="Индекс вовлечённости (исходный)", mode="lines",
                line=dict(color=C_INDEX, width=1, dash="dot"), opacity=0.35, showlegend=False,
            ), row=1, col=1)
        ma_col = f"engagement_index_ma{w}"
        if ma_col in eng.columns:
            fig1.add_trace(go.Scatter(
                x=eng["date"], y=eng[ma_col],
                name=f"Индекс вовлечённости СС{w}", mode="lines",
                line=dict(color=C_INDEX, width=3),
                fill="tozeroy", fillcolor="rgba(0,131,143,0.08)",
                hovertemplate="Дата: %{x|%d.%m.%Y}<br>Индекс: %{y:.1f}<extra></extra>",
            ), row=1, col=1)

        for col, label, color in [
            ("dau",      "ДАП",    C_DAU),
            ("sessions", "Сессии", C_SESSIONS),
        ]:
            ma = f"{col}_ma{w}"
            y  = eng.get(ma, eng.get(col))
            if y is not None:
                fig1.add_trace(go.Scatter(
                    x=eng["date"], y=y,
                    name=f"{label} СС{w}", mode="lines",
                    line=dict(color=color, width=2),
                    hovertemplate=f"Дата: %{{x|%d.%m.%Y}}<br>{label}: %{{y:,.0f}}<extra></extra>",
                ), row=2, col=1)

        fig1.update_layout(
            title="Индекс вовлечённости и его составляющие",
            hovermode="x unified", height=440,
            legend=dict(orientation="h", y=1.05),
        )
        st.plotly_chart(fig1, use_container_width=True)

        last = eng.iloc[-1] if not eng.empty else None
        first = eng.iloc[0]
        if last is not None:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("ДАП (последнее)", f"{last.get('dau', 0):,.0f}",
                      delta=f"{last.get('dau',0)-first.get('dau',0):+.0f}")
            c2.metric("Сессий/день", f"{last.get('sessions', 0):,.0f}")
            c3.metric("Сред. длительность", f"{last.get('avg_duration_min', 0):.1f} мин")
            c4.metric("Индекс вовлечённости", f"{last.get('engagement_index', 0):.1f}")

    st.divider()

    # ── 2. ДАП / НАП / МАП — тренды активности ───────────────────────────────
    st.markdown("## 2. ДАП / НАП / МАП — тренды активности")

    with st.spinner("Загрузка ДАП/НАП/МАП..."):
        dau_df, wau_df, mau_df = svc.dau_wau_mau(
            filters.date_from, filters.date_to, rolling=filters.rolling_window
        )

    if dau_df.empty:
        _empty()
    else:
        w = filters.rolling_window
        fig2 = go.Figure()

        if not dau_df.empty:
            fig2.add_trace(go.Scatter(
                x=dau_df["date"], y=dau_df["dau"],
                name="ДАП (исходный)", mode="lines",
                line=dict(color=C_DAU, width=1, dash="dot"), opacity=0.3, showlegend=False,
            ))
            ma = f"dau_ma{w}"
            if ma in dau_df.columns:
                fig2.add_trace(go.Scatter(
                    x=dau_df["date"], y=dau_df[ma],
                    name=f"ДАП СС{w}", mode="lines",
                    line=dict(color=C_DAU, width=2.5),
                    hovertemplate="Дата: %{x|%d.%m.%Y}<br>ДАП: %{y:,.0f}<extra></extra>",
                ))

        if not wau_df.empty:
            ma = f"wau_ma{w}"
            y  = wau_df[ma] if ma in wau_df.columns else wau_df["wau"]
            fig2.add_trace(go.Scatter(
                x=wau_df["date"], y=y,
                name=f"НАП СС{w}", mode="lines",
                line=dict(color=C_WAU, width=2, dash="dash"),
                hovertemplate="Неделя: %{x|%d.%m.%Y}<br>НАП: %{y:,.0f}<extra></extra>",
            ))

        if not mau_df.empty:
            fig2.add_trace(go.Scatter(
                x=mau_df["date"], y=mau_df["mau"],
                name="МАП", mode="lines+markers",
                line=dict(color=C_MAU, width=2.5),
                marker=dict(size=8, color=C_MAU),
                hovertemplate="Месяц: %{x|%b %Y}<br>МАП: %{y:,.0f}<extra></extra>",
            ))

        fig2.update_layout(
            title="ДАП / НАП / МАП — динамика уникальных пользователей",
            xaxis_title="Дата", yaxis_title="Уникальных пользователей",
            hovermode="x unified",
            legend=dict(orientation="h", y=1.05),
            height=380,
        )
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # ── 3. Поведенческая интенсивность ───────────────────────────────────────
    st.markdown("## 3. Поведенческая интенсивность")
    st.caption("Сессий на пользователя · Средняя длительность · Событий на сессию — как меняется «глубина» взаимодействия.")

    if not eng.empty:
        w = filters.rolling_window
        fig3 = make_subplots(
            rows=1, cols=3, shared_xaxes=False, horizontal_spacing=0.07,
            subplot_titles=("Сессий / пользователь", "Длительность (мин)", "Событий / сессия"),
        )
        for col_idx, (col, label, color) in enumerate([
            ("sessions_per_user",   "Сессий / польз.",   C_SESSIONS),
            ("avg_duration_min",    "Длительность (мин)", C_DURATION),
            ("events_per_session",  "Событий / сессия",  C_EVENTS),
        ], start=1):
            ma_col = f"{col}_ma{w}"
            raw_y = eng.get(col)
            ma_y  = eng.get(ma_col)
            if raw_y is None:
                continue
            fig3.add_trace(go.Scatter(
                x=eng["date"], y=raw_y, name=label + " (исходный)",
                mode="lines", line=dict(color=color, width=1, dash="dot"),
                opacity=0.3, showlegend=False,
                hovertemplate=f"{label}: %{{y:.1f}}<extra></extra>",
            ), row=1, col=col_idx)
            if ma_y is not None:
                fig3.add_trace(go.Scatter(
                    x=eng["date"], y=ma_y, name=f"{label} СС{w}",
                    mode="lines", line=dict(color=color, width=2.5),
                    fill="tozeroy", fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.06)",
                    hovertemplate=f"Дата: %{{x|%d.%m.%Y}}<br>{label}: %{{y:.2f}}<extra></extra>",
                ), row=1, col=col_idx)

        fig3.update_layout(height=340, showlegend=False, hovermode="x unified")
        st.plotly_chart(fig3, use_container_width=True)
    else:
        _empty()

    st.divider()

    # ── 4. Кривые освоения разделов ──────────────────────────────────────────
    st.markdown("## 4. Кривые освоения разделов")
    st.caption("Как менялась популярность разных разделов сайта во времени.")

    with st.spinner("Загрузка данных разделов..."):
        sections = svc.section_adoption(
            filters.date_from, filters.date_to,
            granularity=filters.granularity,
            rolling=filters.rolling_window,
        )

    if sections.empty:
        _empty()
    else:
        w = filters.rolling_window
        fig4 = go.Figure()
        for section, grp in sections.groupby("section"):
            color = SECTION_COLORS.get(section, "#888888")
            label = SECTION_LABELS.get(section, section.capitalize())
            ma_col = f"visits_ma{w}"
            y = grp[ma_col] if ma_col in grp.columns else grp["visits"]
            fig4.add_trace(go.Scatter(
                x=grp["date"], y=y,
                name=label, mode="lines",
                line=dict(color=color, width=2),
                hovertemplate=f"{label}: %{{y:,.0f}} посещений<br>%{{x|%d.%m.%Y}}<extra></extra>",
            ))

        fig4.update_layout(
            title="Динамика использования разделов сайта",
            xaxis_title="Дата", yaxis_title="Посещений (СС)",
            hovermode="x unified",
            legend=dict(orientation="h", y=1.05),
            height=380,
        )
        st.plotly_chart(fig4, use_container_width=True)

    st.divider()

    # ── 5. Тепловая карта активности (час × день недели) ─────────────────────
    st.markdown("## 5. Тепловая карта активности")
    st.caption("Когда студенты заходят на платформу — разбивка по часам и дням недели.")

    with st.spinner("Загрузка тепловой карты..."):
        hmap = svc.hourly_heatmap(filters.date_from, filters.date_to)

    if hmap.empty:
        _empty()
    else:
        pivot = hmap.pivot_table(index="dow", columns="hour", values="sessions", fill_value=0)
        pivot.index = [DOW_LABELS[i] if i < len(DOW_LABELS) else str(i) for i in pivot.index]

        fig5 = go.Figure(go.Heatmap(
            z=pivot.values,
            x=[f"{h:02d}:00" for h in pivot.columns],
            y=list(pivot.index),
            colorscale="YlOrRd",
            hovertemplate="День: %{y}<br>Час: %{x}<br>Сессий: %{z:,}<extra></extra>",
            colorbar=dict(title="Сессий"),
        ))
        fig5.update_layout(
            title="Активность по часам и дням недели",
            xaxis_title="Час", yaxis_title="День недели",
            height=300,
        )
        st.plotly_chart(fig5, use_container_width=True)

    st.divider()

    # ── 6. Удержание когорт ───────────────────────────────────────────────────
    st.markdown("## 6. Удержание когорт")
    st.caption("Процент пользователей, вернувшихся на неделе N после первого посещения.")

    with st.spinner("Вычисление удержания..."):
        ret = svc.retention_matrix(filters.date_from, filters.date_to)

    if ret.empty:
        _empty()
    else:
        pivot_ret = ret.pivot_table(
            index="cohort_week", columns="week_num",
            values="retention_pct", fill_value=None,
        )
        pivot_ret.index = pd.to_datetime(pivot_ret.index).strftime("%d.%m.%Y")
        pivot_ret = pivot_ret.head(15)

        fig6 = go.Figure(go.Heatmap(
            z=pivot_ret.values,
            x=[f"Неделя {int(c)}" for c in pivot_ret.columns],
            y=list(pivot_ret.index),
            colorscale="RdYlGn",
            zmin=0, zmax=100,
            hovertemplate="Когорта: %{y}<br>%{x}<br>Удержание: %{z:.1f}%<extra></extra>",
            colorbar=dict(title="%"),
        ))
        fig6.update_layout(
            title="Удержание когорт (% вернувшихся пользователей по неделям)",
            xaxis_title="Неделя после первого визита",
            yaxis_title="Когорта (неделя первого визита)",
            height=max(300, len(pivot_ret) * 25 + 100),
            margin=dict(l=100),
        )
        st.plotly_chart(fig6, use_container_width=True)

    st.divider()

    # ── 7. Навигация пользователей (Граф) ────────────────────────────────────
    st.markdown("## 7. Навигация пользователей (Граф)")
    st.caption("Потоки переходов между разделами сайта. Толщина рёбер — интенсивность переходов.")

    with st.spinner("Построение графа..."):
        transitions = svc.page_transitions(filters.date_from, filters.date_to)

    if transitions.empty or len(transitions) < 3:
        _empty()
    else:
        all_nodes = sorted(set(transitions["from_section"]) | set(transitions["to_section"]))
        n_nodes = len(all_nodes)

        # Круговое расположение узлов
        positions = {
            node: (
                math.cos(2 * math.pi * i / n_nodes),
                math.sin(2 * math.pi * i / n_nodes),
            )
            for i, node in enumerate(all_nodes)
        }

        # Суммарный объём переходов на узел (для размера)
        node_volume: dict[str, int] = {}
        for _, row in transitions.iterrows():
            node_volume[row["from_section"]] = node_volume.get(row["from_section"], 0) + row["transitions"]
            node_volume[row["to_section"]]   = node_volume.get(row["to_section"],   0) + row["transitions"]
        max_vol = max(node_volume.values()) if node_volume else 1

        max_trans = transitions["transitions"].max() if not transitions.empty else 1

        fig7 = go.Figure()

        # Рёбра
        for _, row in transitions.iterrows():
            x0, y0 = positions[row["from_section"]]
            x1, y1 = positions[row["to_section"]]
            lbl_from = SECTION_LABELS.get(row["from_section"], row["from_section"].capitalize())
            lbl_to   = SECTION_LABELS.get(row["to_section"],   row["to_section"].capitalize())
            width = max(0.5, 6 * row["transitions"] / max_trans)
            fig7.add_trace(go.Scatter(
                x=[x0, x1], y=[y0, y1],
                mode="lines",
                line=dict(width=width, color="rgba(150,150,150,0.45)"),
                hovertemplate=f"Из «{lbl_from}» → «{lbl_to}»<br>Переходов: {row['transitions']:,}<extra></extra>",
                showlegend=False,
            ))

        # Узлы
        node_x     = [positions[n][0] for n in all_nodes]
        node_y     = [positions[n][1] for n in all_nodes]
        node_sizes = [20 + 30 * node_volume.get(n, 0) / max_vol for n in all_nodes]
        node_cols  = [SECTION_COLORS.get(n, "#aec7e8") for n in all_nodes]
        node_texts = [SECTION_LABELS.get(n, n.capitalize()) for n in all_nodes]
        node_hover = [
            f"{SECTION_LABELS.get(n, n.capitalize())}<br>Переходов: {node_volume.get(n, 0):,}"
            for n in all_nodes
        ]

        fig7.add_trace(go.Scatter(
            x=node_x, y=node_y,
            mode="markers+text",
            marker=dict(size=node_sizes, color=node_cols,
                        line=dict(width=1.5, color="white")),
            text=node_texts,
            textposition="top center",
            hovertemplate="%{customdata}<extra></extra>",
            customdata=node_hover,
            showlegend=False,
        ))

        fig7.update_layout(
            title="Граф переходов между разделами",
            height=480,
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            margin=dict(l=20, r=20, t=50, b=20),
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig7, use_container_width=True)
