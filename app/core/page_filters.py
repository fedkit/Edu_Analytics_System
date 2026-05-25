"""Боковые панели для каждой страницы — отдельные фильтры."""
from __future__ import annotations

from datetime import date
from typing import Optional

import streamlit as st
from sqlalchemy.engine import Engine

from app.core.filters import FilterState
from app.core.time_aggregation import Granularity

DATA_START = date(2024, 1, 1)
DATA_END   = date(2025, 4, 1)

DATE_PRESETS: dict[str, tuple[date, date]] = {
    "Весь период (2024–2025)": (DATA_START, DATA_END),
    "2024 год":                (date(2024, 1, 1), date(2024, 12, 31)),
    "2025 (янв–апр)":          (date(2025, 1, 1), DATA_END),
    "I полугодие 2024":        (date(2024, 1, 1), date(2024, 6, 30)),
    "II полугодие 2024":       (date(2024, 7, 1), date(2024, 12, 31)),
    "Произвольный период":     (DATA_START, DATA_END),
}


def _date_block(default: str = "Весь период (2024–2025)") -> tuple[date, date]:
    preset = st.selectbox("Период", list(DATE_PRESETS.keys()),
                          index=list(DATE_PRESETS.keys()).index(default))
    d_from_def, d_to_def = DATE_PRESETS[preset]
    if preset == "Произвольный период":
        d_from = st.date_input("С",  value=d_from_def, min_value=DATA_START, max_value=DATA_END)
        d_to   = st.date_input("По", value=d_to_def,   min_value=DATA_START, max_value=DATA_END)
    else:
        d_from, d_to = d_from_def, d_to_def
        st.caption(f"{d_from.strftime('%d.%m.%Y')} — {d_to.strftime('%d.%m.%Y')}")
    if d_from > d_to:
        st.error("Начальная дата позже конечной")
        d_from = d_to
    return d_from, d_to


def _rolling_block(options: list[int] | None = None, default: int = 7) -> int:
    opts = options or [3, 7, 14, 21, 30]
    return st.select_slider("Окно сглаживания (дней)", options=opts, value=default)


def _refresh_block() -> None:
    if st.button("Обновить данные", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ── 1. Академическая аналитика ────────────────────────────────────────────────

def render_academic_filters(engine: Engine) -> FilterState:
    with st.sidebar:
        st.markdown("## Академическая аналитика")
        st.divider()

        st.markdown("#### Период")
        d_from, d_to = _date_block()

        st.markdown("#### Уровень анализа")
        level_map = {
            "Все участники": "all",
            "Факультет":     "faculty",
            "Группа":        "group",
            "Студент":       "student",
        }
        level_lbl = st.radio("", list(level_map.keys()), index=0)
        level: str = level_map[level_lbl]

        sel_fac_id, sel_fac_name = None, None
        sel_grp_id, sel_grp_name = None, None
        sel_stu_id, sel_stu_name = None, None

        try:
            from app.queries.postgres_queries import (
                get_faculties, get_study_groups, search_users,
                get_subjects, get_semesters, get_courses,
            )
        except Exception:
            get_faculties = get_study_groups = search_users = None
            get_subjects = get_semesters = get_courses = None

        if level == "faculty" and get_faculties:
            try:
                fac_df   = get_faculties(engine)
                fac_opts = list(zip(fac_df["faculty_id"], fac_df["faculty_name"]))
                if fac_opts:
                    lbls = [o[1] for o in fac_opts]
                    idx  = st.selectbox("Факультет", range(len(lbls)), format_func=lambda i: lbls[i])
                    sel_fac_id, sel_fac_name = fac_opts[idx]
            except Exception:
                pass

        elif level == "group" and get_study_groups:
            try:
                grp_df   = get_study_groups(engine)
                grp_opts = list(zip(grp_df["group_id"], grp_df["group_name"]))
                if grp_opts:
                    lbls = [o[1] for o in grp_opts]
                    idx  = st.selectbox("Группа", range(len(lbls)), format_func=lambda i: lbls[i])
                    sel_grp_id, sel_grp_name = grp_opts[idx]
            except Exception:
                pass

        elif level == "student" and search_users:
            q = st.text_input("Поиск студента", placeholder="Фамилия или никнейм")
            if q and len(q) >= 2:
                try:
                    found = search_users(engine, q)
                    if not found.empty:
                        def _lbl(r) -> str:
                            nick = r.get("user_nickname", "")
                            return f"{r['surname']} {r['first_name']} [{nick}]"
                        opts    = {_lbl(r): int(r["user_id"]) for _, r in found.iterrows()}
                        chosen  = st.selectbox("Студент", list(opts.keys()))
                        sel_stu_id   = opts[chosen]
                        sel_stu_name = chosen
                    else:
                        st.caption("Студенты не найдены")
                except Exception:
                    pass

        st.divider()
        st.markdown("#### Дополнительные фильтры")

        sel_subj_id, sel_subj_name = None, None
        if get_subjects:
            try:
                subj_df   = get_subjects(engine)
                subj_opts = [(None, "Все предметы")] + list(zip(subj_df["subject_id"], subj_df["subject_name"]))
                lbls      = [o[1] for o in subj_opts]
                idx       = st.selectbox("Предмет", range(len(lbls)), format_func=lambda i: lbls[i])
                sel_subj_id   = subj_opts[idx][0]
                sel_subj_name = subj_opts[idx][1] if sel_subj_id else None
            except Exception:
                pass

        sel_semester = None
        if get_semesters:
            try:
                sem_df = get_semesters(engine)
                if not sem_df.empty:
                    vals  = [None] + sem_df["semester"].tolist()
                    lbls  = ["Все семестры"] + [f"Семестр {s}" for s in vals[1:]]
                    idx   = st.selectbox("Семестр", range(len(lbls)), format_func=lambda i: lbls[i])
                    sel_semester = vals[idx]
            except Exception:
                pass

        sel_course = None
        if get_courses:
            try:
                crs_df = get_courses(engine)
                if not crs_df.empty:
                    vals  = [None] + crs_df["course"].tolist()
                    lbls  = ["Все курсы"] + [f"{c} курс" for c in vals[1:]]
                    idx   = st.selectbox("Курс", range(len(lbls)), format_func=lambda i: lbls[i])
                    sel_course = vals[idx]
            except Exception:
                pass

        st.markdown("#### Сглаживание")
        rolling = _rolling_block()

        st.divider()
        _refresh_block()
        st.caption(f"Данные за {(d_to - d_from).days + 1} дней")

    return FilterState(
        date_from=d_from, date_to=d_to,
        granularity="daily", compare_prev=False,
        faculty_id=sel_fac_id,  faculty_name=sel_fac_name,
        group_id=sel_grp_id,    group_name=sel_grp_name,
        rolling_window=rolling,
        analysis_level=level,
        student_id=sel_stu_id,    student_name=sel_stu_name,
        subject_id=sel_subj_id,   subject_name=sel_subj_name,
        semester_filter=sel_semester,
        course_filter=sel_course,
    )


# ── 2. Аналитика использования ────────────────────────────────────────────────

def render_usage_filters() -> FilterState:
    with st.sidebar:
        st.markdown("## Пользовательская аналитика")
        st.divider()

        st.markdown("#### Период")
        d_from, d_to = _date_block()

        st.markdown("#### Гранулярность")
        gran_map = {"По дням": "daily", "По неделям": "weekly", "По месяцам": "monthly"}
        gran_lbl = st.radio("", list(gran_map.keys()), index=0, horizontal=True)
        granularity: Granularity = gran_map[gran_lbl]

        st.markdown("#### Сглаживание")
        rolling = _rolling_block()

        st.divider()
        _refresh_block()
        st.caption(f"Данные за {(d_to - d_from).days + 1} дней")

    return FilterState(
        date_from=d_from, date_to=d_to,
        granularity=granularity, compare_prev=False,
        rolling_window=rolling,
    )


# ── 3. Корреляция обучения ────────────────────────────────────────────────────

def render_correlation_filters(engine: Engine) -> FilterState:
    with st.sidebar:
        st.markdown("## Корреляция обучения")
        st.divider()

        st.markdown("#### Период")
        d_from, d_to = _date_block()

        st.markdown("#### Уровень анализа")
        level_map = {"Все участники": "all", "Факультет": "faculty", "Группа": "group"}
        level_lbl = st.radio("", list(level_map.keys()), index=0)
        level: str = level_map[level_lbl]

        sel_fac_id, sel_fac_name = None, None
        sel_grp_id, sel_grp_name = None, None

        try:
            from app.queries.postgres_queries import get_faculties, get_study_groups
        except Exception:
            get_faculties = get_study_groups = None

        if level == "faculty" and get_faculties:
            try:
                fac_df   = get_faculties(engine)
                fac_opts = list(zip(fac_df["faculty_id"], fac_df["faculty_name"]))
                if fac_opts:
                    lbls = [o[1] for o in fac_opts]
                    idx  = st.selectbox("Факультет", range(len(lbls)), format_func=lambda i: lbls[i])
                    sel_fac_id, sel_fac_name = fac_opts[idx]
            except Exception:
                pass

        elif level == "group" and get_study_groups:
            try:
                grp_df   = get_study_groups(engine)
                grp_opts = list(zip(grp_df["group_id"], grp_df["group_name"]))
                if grp_opts:
                    lbls = [o[1] for o in grp_opts]
                    idx  = st.selectbox("Группа", range(len(lbls)), format_func=lambda i: lbls[i])
                    sel_grp_id, sel_grp_name = grp_opts[idx]
            except Exception:
                pass

        st.divider()
        st.markdown("#### Параметры корреляции")

        rolling = st.select_slider(
            "Скользящее окно (дней)",
            options=[14, 21, 30, 60, 90],
            value=30,
        )

        corr_method = st.radio(
            "Метод корреляции",
            ["pearson", "spearman"],
            format_func=lambda x: {"pearson": "Пирсон", "spearman": "Спирмен"}[x],
            horizontal=True,
        )

        st.divider()
        _refresh_block()
        st.caption(f"Данные за {(d_to - d_from).days + 1} дней")

    return FilterState(
        date_from=d_from, date_to=d_to,
        granularity="daily", compare_prev=False,
        rolling_window=rolling,
        analysis_level=level,
        faculty_id=sel_fac_id, faculty_name=sel_fac_name,
        group_id=sel_grp_id,   group_name=sel_grp_name,
        corr_method=corr_method,
    )
