"""Academic Analytics page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components.charts import (
    PLOTLY_CONFIG, bar_chart, box_plot, line_chart, scatter_chart,
)
from app.components.filters import FilterState
from app.repositories.academic_repo import AcademicRepository
from app.services.trend_service import add_moving_average


def render(f: FilterState, academic: AcademicRepository) -> None:
    st.title("🎓 Академическая аналитика")
    st.caption(f"Период: {f.start_date} — {f.end_date}")

    tabs = st.tabs(["Успеваемость", "Посещаемость", "Экзамены"])

    # ─── TAB 1: Performance ───────────────────────────────────────────────────
    with tabs[0]:
        st.subheader("Тренд среднего балла")
        gpa_ts  = academic.get_gpa_timeseries(f.start_date, f.end_date)
        pass_ts = academic.get_pass_rate_timeseries(f.start_date, f.end_date)
        fac_gpa = academic.get_gpa_by_faculty(f.start_date, f.end_date)

        c1, c2 = st.columns(2)
        with c1:
            if not gpa_ts.empty:
                gpa_ts = add_moving_average(gpa_ts, "avg_score_pct", 7)
                fig = line_chart(
                    gpa_ts, "score_date", "avg_score_pct",
                    title="Средний балл (%) по дням",
                    y_label="Балл (%)", ma_col="avg_score_pct_ma7",
                )
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        with c2:
            if not pass_ts.empty:
                pass_ts = add_moving_average(pass_ts, "pass_rate", 7)
                fig = line_chart(
                    pass_ts, "score_date", "pass_rate",
                    title="Pass Rate (%) по дням",
                    y_label="Доля сдавших (%)", ma_col="pass_rate_ma7",
                )
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        st.subheader("Средний балл по факультетам")
        if not fac_gpa.empty:
            fig = bar_chart(
                fac_gpa.sort_values("avg_score_pct"),
                x="avg_score_pct", y="faculty_name",
                title="Средний балл (%) — топ факультетов",
                horizontal=True,
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        # Score distribution
        st.subheader("Распределение оценок")
        scores_raw = academic.get_scores_timeseries(f.start_date, f.end_date)
        if not scores_raw.empty:
            fig = box_plot(
                scores_raw, x="score_type", y="score_pct",
                title="Распределение баллов (%) по типу оценки",
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

            # Monthly aggregation
            scores_raw["month"] = pd.to_datetime(scores_raw["score_date"]).dt.to_period("M").dt.start_time
            monthly = scores_raw.groupby("month")["score_pct"].mean().reset_index()
            monthly.columns = ["month", "avg_score_pct"]
            fig = line_chart(monthly, "month", "avg_score_pct",
                             title="Средний балл по месяцам", area=True)
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    # ─── TAB 2: Attendance ────────────────────────────────────────────────────
    with tabs[1]:
        st.subheader("Тренд посещаемости")
        att_ts  = academic.get_attendance_timeseries(f.start_date, f.end_date)
        att_sub = academic.get_attendance_by_subject(f.start_date, f.end_date)

        if not att_ts.empty:
            att_ts = add_moving_average(att_ts, "attendance_pct", 7)
            fig = line_chart(
                att_ts, "lesson_date", "attendance_pct",
                title="Посещаемость (%) по дням",
                y_label="Посещаемость (%)", ma_col="attendance_pct_ma7",
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        st.subheader("Посещаемость по предметам")
        if not att_sub.empty:
            fig = bar_chart(
                att_sub.sort_values("attendance_pct").tail(20),
                x="attendance_pct", y="subject_name",
                title="Посещаемость (%) — топ предметов",
                horizontal=True,
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

            low_att = att_sub[att_sub["attendance_pct"] < 50]
            if not low_att.empty:
                st.warning(f"Предметы с посещаемостью < 50%: {len(low_att)}")
                st.dataframe(
                    low_att[["subject_name", "attendance_pct", "total"]].rename(
                        columns={"subject_name": "Предмет", "attendance_pct": "Посещ. (%)", "total": "Записей"}
                    ),
                    hide_index=True, use_container_width=True,
                )

    # ─── TAB 3: Exams ─────────────────────────────────────────────────────────
    with tabs[2]:
        st.subheader("Статистика экзаменов")
        exam_stats = academic.get_exam_statistics()

        if not exam_stats.empty:
            c1, c2 = st.columns(2)
            with c1:
                fig = bar_chart(
                    exam_stats.sort_values("pass_rate_pct", ascending=True).tail(20),
                    x="pass_rate_pct", y="subject_name",
                    title="Pass Rate по предметам (%)",
                    horizontal=True,
                )
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

            with c2:
                fig = bar_chart(
                    exam_stats.sort_values("registered_count", ascending=False).head(15),
                    x="subject_name", y=["registered_count", "passed_count", "failed_count"],
                    title="Зарегистрировано / Сдало / Не сдало",
                    stacked=False,
                )
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

            # Timeline
            exam_stats["exam_date"] = pd.to_datetime(exam_stats["exam_date"])
            exam_time = (
                exam_stats.groupby("exam_date")["pass_rate_pct"].mean().reset_index()
            )
            if len(exam_time) > 1:
                fig = line_chart(exam_time, "exam_date", "pass_rate_pct",
                                 title="Средний pass rate по дате экзамена",
                                 y_label="Pass Rate (%)")
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

            with st.expander("Все экзамены"):
                st.dataframe(exam_stats, use_container_width=True)
