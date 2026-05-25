"""Боковая панель фильтров: диапазон дат, гранулярность, факультет, группа."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

import streamlit as st

from app.core.time_aggregation import Granularity

# Диапазон данных в БД
DATA_START = date(2024, 1, 1)
DATA_END = date(2025, 4, 1)

DATE_PRESETS: dict[str, tuple[date, date]] = {
    "Весь период (2024–2025)": (DATA_START, DATA_END),
    "2024 год":                (date(2024, 1, 1), date(2024, 12, 31)),
    "2025 (янв–апр)":          (date(2025, 1, 1), DATA_END),
    "I полугодие 2024":        (date(2024, 1, 1), date(2024, 6, 30)),
    "II полугодие 2024":       (date(2024, 7, 1), date(2024, 12, 31)),
    "Произвольный период":     (DATA_START, DATA_END),
}

DEFAULT_PRESET = "Весь период (2024–2025)"


@dataclass
class FilterState:
    date_from: date
    date_to: date
    granularity: Granularity
    compare_prev: bool
    faculty_id: Optional[int] = None
    faculty_name: Optional[str] = None
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    rolling_window: int = 7
    # Academic analytics filters
    analysis_level: str = "all"          # "all" | "faculty" | "group" | "student"
    student_id: Optional[int] = None
    student_name: Optional[str] = None
    subject_id: Optional[int] = None
    subject_name: Optional[str] = None
    semester_filter: Optional[int] = None
    course_filter: Optional[int] = None
    corr_method: str = "pearson"     # "pearson" | "spearman"

    @property
    def prev_date_from(self) -> date:
        delta = self.date_to - self.date_from
        return self.date_from - delta

    @property
    def prev_date_to(self) -> date:
        from datetime import timedelta
        return self.date_from - timedelta(days=1)


def render_sidebar(
    faculties: list[tuple] = [],
    groups: list[tuple] = [],
) -> FilterState:
    """Отрисовать боковую панель и вернуть состояние фильтров."""
    with st.sidebar:
        st.markdown("## Параметры")

        # ── Период ────────────────────────────────────────────────────────────
        st.markdown("#### Период анализа")
        preset_names = list(DATE_PRESETS.keys())
        preset_idx = preset_names.index(DEFAULT_PRESET)
        preset_choice = st.selectbox("Шаблон", preset_names, index=preset_idx)

        d_from_def, d_to_def = DATE_PRESETS[preset_choice]

        if preset_choice == "Произвольный период":
            d_from = st.date_input("С", value=d_from_def, min_value=DATA_START, max_value=DATA_END)
            d_to   = st.date_input("По", value=d_to_def,   min_value=DATA_START, max_value=DATA_END)
        else:
            d_from, d_to = d_from_def, d_to_def
            st.caption(f"{d_from.strftime('%d.%m.%Y')} — {d_to.strftime('%d.%m.%Y')}")

        if d_from > d_to:
            st.error("Начальная дата позже конечной")
            d_from = d_to

        # ── Гранулярность ────────────────────────────────────────────────────
        st.markdown("#### Гранулярность")
        gran_map = {"По дням": "daily", "По неделям": "weekly", "По месяцам": "monthly"}
        gran_lbl = st.radio("", list(gran_map.keys()), index=0, horizontal=True)
        granularity: Granularity = gran_map[gran_lbl]

        # ── Скользящее окно ───────────────────────────────────────────────────
        rolling_window = st.select_slider(
            "Окно сглаживания (дней)",
            options=[3, 7, 14, 21, 30],
            value=7,
        )

        compare_prev = st.checkbox("Сравнить с предыдущим периодом", value=False)

        st.divider()

        # ── Факультет ─────────────────────────────────────────────────────────
        fac_options = [(None, "Все факультеты")] + [(fid, fname) for fid, fname in faculties]
        fac_labels  = [o[1] for o in fac_options]
        fac_idx = st.selectbox("Факультет", range(len(fac_labels)), format_func=lambda i: fac_labels[i])
        sel_fac_id   = fac_options[fac_idx][0]
        sel_fac_name = fac_options[fac_idx][1] if sel_fac_id else None

        # ── Группа ───────────────────────────────────────────────────────────
        grp_options = [(None, "Все группы")] + [(gid, gname) for gid, gname in groups]
        grp_labels  = [o[1] for o in grp_options]
        grp_idx = st.selectbox("Группа", range(len(grp_labels)), format_func=lambda i: grp_labels[i])
        sel_grp_id   = grp_options[grp_idx][0]
        sel_grp_name = grp_options[grp_idx][1] if sel_grp_id else None

        st.divider()

        # ── Refresh ───────────────────────────────────────────────────────────
        if st.button("Обновить данные", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.caption(f"Данные за {(d_to - d_from).days + 1} дней")

    return FilterState(
        date_from=d_from,
        date_to=d_to,
        granularity=granularity,
        compare_prev=compare_prev,
        faculty_id=sel_fac_id,
        faculty_name=sel_fac_name,
        group_id=sel_grp_id,
        group_name=sel_grp_name,
        rolling_window=rolling_window,
    )
