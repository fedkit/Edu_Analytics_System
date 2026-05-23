"""Global sidebar filters shared across all pages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import streamlit as st

from app.utils.helpers import get_preset_dates

GRANULARITIES = ["daily", "weekly", "monthly"]
GRANULARITY_LABELS = {"daily": "День", "weekly": "Неделя", "monthly": "Месяц"}

PRESETS = {
    "last_7":        "Последние 7 дней",
    "last_30":       "Последние 30 дней",
    "last_90":       "Последние 90 дней",
    "this_semester": "Текущий семестр",
    "prev_semester": "Прошлый семестр",
    "custom":        "Произвольный период",
}

COMPARISON_OPTIONS = {
    "none":       "Без сравнения",
    "prev_period": "Предыдущий период",
    "yoy":        "Год к году",
}


@dataclass
class FilterState:
    start_date: date
    end_date: date
    granularity: str
    comparison: str
    faculty_ids: list[int]
    group_ids: list[int]
    subject_ids: list[int]
    statuses: list[str]
    device_types: list[str]


def render_sidebar(
    faculties: list[tuple[int, str]] | None = None,
    groups: list[tuple[int, str]] | None = None,
    subjects: list[tuple[int, str]] | None = None,
) -> FilterState:
    """Render sidebar filters and return the current FilterState."""

    with st.sidebar:
        st.header("Фильтры")

        # ── Date range ────────────────────────────────────
        preset_key = st.selectbox(
            "Период", list(PRESETS.keys()),
            format_func=lambda k: PRESETS[k],
            index=1, key="sidebar_preset",
        )
        if preset_key == "custom":
            col1, col2 = st.columns(2)
            start = col1.date_input("С", value=date.today() - timedelta(days=29), key="date_start")
            end   = col2.date_input("По", value=date.today(), key="date_end")
        else:
            start, end = get_preset_dates(preset_key)

        # ── Granularity ───────────────────────────────────
        gran = st.selectbox(
            "Гранулярность",
            GRANULARITIES,
            format_func=lambda k: GRANULARITY_LABELS[k],
            index=0, key="sidebar_gran",
        )

        # ── Comparison ────────────────────────────────────
        comparison = st.selectbox(
            "Сравнение",
            list(COMPARISON_OPTIONS.keys()),
            format_func=lambda k: COMPARISON_OPTIONS[k],
            index=0, key="sidebar_compare",
        )

        st.divider()

        # ── Faculty ───────────────────────────────────────
        selected_faculty_ids: list[int] = []
        if faculties:
            fac_options = {fid: name for fid, name in faculties}
            selected = st.multiselect(
                "Факультет", list(fac_options.keys()),
                format_func=lambda k: fac_options[k],
                key="sidebar_faculty",
            )
            selected_faculty_ids = selected

        # ── Study group ───────────────────────────────────
        selected_group_ids: list[int] = []
        if groups:
            grp_options = {gid: name for gid, name in groups}
            selected = st.multiselect(
                "Учебная группа", list(grp_options.keys()),
                format_func=lambda k: grp_options[k],
                key="sidebar_group",
            )
            selected_group_ids = selected

        # ── Subject ───────────────────────────────────────
        selected_subject_ids: list[int] = []
        if subjects:
            subj_options = {sid: name for sid, name in subjects}
            selected = st.multiselect(
                "Предмет", list(subj_options.keys()),
                format_func=lambda k: subj_options[k],
                key="sidebar_subject",
            )
            selected_subject_ids = selected

        # ── Status ────────────────────────────────────────
        statuses = st.multiselect(
            "Статус студента",
            ["Обучается", "Академический отпуск", "Отчислен", "Выпускник"],
            default=["Обучается"],
            key="sidebar_status",
        )

        # ── Device type ───────────────────────────────────
        device_types = st.multiselect(
            "Устройство",
            ["desktop", "mobile", "tablet"],
            key="sidebar_device",
        )

        st.divider()

        # ── Refresh ───────────────────────────────────────
        if st.button("🔄 Обновить данные", use_container_width=True, key="refresh_btn"):
            from app.utils.cache import invalidate_all
            invalidate_all()
            st.rerun()

    return FilterState(
        start_date=start,
        end_date=end,
        granularity=gran,
        comparison=comparison,
        faculty_ids=selected_faculty_ids,
        group_ids=selected_group_ids,
        subject_ids=selected_subject_ids,
        statuses=statuses,
        device_types=device_types,
    )
