"""PostgreSQL repository — all academic data queries."""

from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.utils.cache import get_ttl
from app.utils.logger import get_logger

log = get_logger(__name__)


class AcademicRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def _read(self, sql: str, params: dict | None = None) -> pd.DataFrame:
        with self.engine.connect() as conn:
            return pd.read_sql(text(sql), conn, params=params or {})

    # ── Dimensions / filters ──────────────────────────────────────────────────

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_faculties(_self) -> pd.DataFrame:
        return _self._read("SELECT faculty_id, faculty_name FROM edu.faculty ORDER BY faculty_name")

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_departments(_self, faculty_id: Optional[int] = None) -> pd.DataFrame:
        if faculty_id:
            return _self._read(
                "SELECT department_id, department_name FROM edu.department "
                "WHERE faculty_id = :fid ORDER BY department_name",
                {"fid": faculty_id},
            )
        return _self._read(
            "SELECT d.department_id, d.department_name, f.faculty_name "
            "FROM edu.department d JOIN edu.faculty f USING (faculty_id) "
            "ORDER BY d.department_name"
        )

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_study_groups(_self) -> pd.DataFrame:
        return _self._read(
            """
            SELECT sg.group_id, sg.group_name, sg.enrollment_year, sg.course,
                   sg.semestr, p.profile, p.speciality,
                   f.faculty_name, d.department_name
            FROM edu.study_group sg
            JOIN edu.program    p  USING (program_id)
            JOIN edu.department d  USING (department_id)
            JOIN edu.faculty    f  USING (faculty_id)
            ORDER BY sg.group_name
            """
        )

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_subjects(_self) -> pd.DataFrame:
        return _self._read(
            "SELECT subject_id, subject_name, semestr, credit_hours, type "
            "FROM edu.subject ORDER BY subject_name"
        )

    # ── Users ─────────────────────────────────────────────────────────────────

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_users(_self) -> pd.DataFrame:
        return _self._read(
            """
            SELECT u.user_id, u.user_nickname, u.first_name, u.surname,
                   u.middle_name, u.gender, u.enrollment_year,
                   u.funding_type, u.dormitory_resident,
                   u.status, u.current_course,
                   sg.group_name,
                   f.faculty_name,
                   d.department_name
            FROM edu."user" u
            LEFT JOIN edu.user_study_group usg USING (user_id)
            LEFT JOIN edu.study_group sg        USING (group_id)
            LEFT JOIN edu.program     p         USING (program_id)
            LEFT JOIN edu.department  d         USING (department_id)
            LEFT JOIN edu.faculty     f         USING (faculty_id)
            """
        )

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_user_by_id(_self, user_id: int) -> pd.DataFrame:
        return _self._read(
            """
            SELECT u.user_id, u.user_nickname, u.first_name, u.surname,
                   u.middle_name, u.gender, u.birth_date,
                   u.enrollment_year, u.funding_type,
                   u.dormitory_resident, u.status, u.current_course,
                   sg.group_name, f.faculty_name, d.department_name
            FROM edu."user" u
            LEFT JOIN edu.user_study_group usg USING (user_id)
            LEFT JOIN edu.study_group sg        USING (group_id)
            LEFT JOIN edu.program     p         USING (program_id)
            LEFT JOIN edu.department  d         USING (department_id)
            LEFT JOIN edu.faculty     f         USING (faculty_id)
            WHERE u.user_id = :uid
            """,
            {"uid": user_id},
        )

    # ── Performance view ──────────────────────────────────────────────────────

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_student_performance(_self) -> pd.DataFrame:
        return _self._read("SELECT * FROM edu.student_performance_view")

    # ── Scores ────────────────────────────────────────────────────────────────

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_scores_timeseries(
        _self, start: date, end: date, subject_id: Optional[int] = None
    ) -> pd.DataFrame:
        sql = """
            SELECT sc.score_date, sc.user_id, sc.subject_id,
                   s.subject_name, sc.score, sc.max_score, sc.is_passed,
                   sc.score_type, sc.module,
                   ROUND(sc.score::NUMERIC / NULLIF(sc.max_score,0) * 100, 2) AS score_pct
            FROM edu.score sc
            JOIN edu.subject s USING (subject_id)
            WHERE sc.score_date BETWEEN :s AND :e
        """
        params: dict = {"s": start, "e": end}
        if subject_id:
            sql += " AND sc.subject_id = :sid"
            params["sid"] = subject_id
        return _self._read(sql, params)

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_scores_for_user(_self, user_id: int) -> pd.DataFrame:
        return _self._read(
            """
            SELECT sc.score_id, sc.score_date, sc.subject_id,
                   s.subject_name, sc.score, sc.max_score, sc.is_passed,
                   sc.score_type, sc.module, sc.attempt_number,
                   ROUND(sc.score::NUMERIC / NULLIF(sc.max_score,0) * 100, 2) AS score_pct
            FROM edu.score sc
            JOIN edu.subject s USING (subject_id)
            WHERE sc.user_id = :uid
            ORDER BY sc.score_date
            """,
            {"uid": user_id},
        )

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_gpa_timeseries(_self, start: date, end: date) -> pd.DataFrame:
        """Daily average score_pct — proxy for GPA trend."""
        return _self._read(
            """
            SELECT sc.score_date,
                   ROUND(AVG(sc.score::NUMERIC / NULLIF(sc.max_score,0) * 100), 2) AS avg_score_pct,
                   COUNT(sc.score_id) AS score_count
            FROM edu.score sc
            WHERE sc.score_date BETWEEN :s AND :e
            GROUP BY sc.score_date
            ORDER BY sc.score_date
            """,
            {"s": start, "e": end},
        )

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_gpa_by_faculty(_self, start: date, end: date) -> pd.DataFrame:
        return _self._read(
            """
            SELECT f.faculty_name,
                   ROUND(AVG(sc.score::NUMERIC / NULLIF(sc.max_score,0) * 100), 2) AS avg_score_pct
            FROM edu.score sc
            JOIN edu."user" u  USING (user_id)
            JOIN edu.user_study_group usg ON usg.user_id = u.user_id
            JOIN edu.study_group sg       ON sg.group_id = usg.group_id
            JOIN edu.program p            ON p.program_id = sg.program_id
            JOIN edu.department d         ON d.department_id = p.department_id
            JOIN edu.faculty f            ON f.faculty_id = d.faculty_id
            WHERE sc.score_date BETWEEN :s AND :e
            GROUP BY f.faculty_name
            ORDER BY avg_score_pct DESC
            """,
            {"s": start, "e": end},
        )

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_pass_rate_timeseries(_self, start: date, end: date) -> pd.DataFrame:
        return _self._read(
            """
            SELECT score_date,
                   ROUND(SUM(is_passed::INT)::NUMERIC / NULLIF(COUNT(*),0) * 100, 2) AS pass_rate,
                   COUNT(*) AS total
            FROM edu.score
            WHERE score_date BETWEEN :s AND :e
            GROUP BY score_date
            ORDER BY score_date
            """,
            {"s": start, "e": end},
        )

    # ── Attendance ────────────────────────────────────────────────────────────

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_attendance_timeseries(_self, start: date, end: date) -> pd.DataFrame:
        return _self._read(
            """
            SELECT lesson_date,
                   ROUND(SUM(is_present::INT)::NUMERIC / NULLIF(COUNT(*),0) * 100, 2) AS attendance_pct,
                   COUNT(*) AS total_records
            FROM edu.attendance
            WHERE lesson_date BETWEEN :s AND :e
            GROUP BY lesson_date
            ORDER BY lesson_date
            """,
            {"s": start, "e": end},
        )

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_attendance_by_subject(_self, start: date, end: date) -> pd.DataFrame:
        return _self._read(
            """
            SELECT s.subject_name,
                   ROUND(SUM(a.is_present::INT)::NUMERIC / NULLIF(COUNT(*),0) * 100, 2) AS attendance_pct,
                   COUNT(*) AS total
            FROM edu.attendance a
            JOIN edu.subject s USING (subject_id)
            WHERE a.lesson_date BETWEEN :s AND :e
            GROUP BY s.subject_name
            ORDER BY attendance_pct
            """,
            {"s": start, "e": end},
        )

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_attendance_for_user(_self, user_id: int) -> pd.DataFrame:
        return _self._read(
            """
            SELECT a.attendance_id, a.lesson_date, a.lesson_type,
                   a.is_present, s.subject_name
            FROM edu.attendance a
            JOIN edu.subject s USING (subject_id)
            WHERE a.user_id = :uid
            ORDER BY a.lesson_date
            """,
            {"uid": user_id},
        )

    # ── Exams ─────────────────────────────────────────────────────────────────

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_exam_statistics(_self) -> pd.DataFrame:
        return _self._read("SELECT * FROM edu.exam_statistics_view ORDER BY exam_date")

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_exams_for_user(_self, user_id: int) -> pd.DataFrame:
        return _self._read(
            """
            SELECT e.exam_id, e.exam_date, e.exam_type, e.passed_type,
                   s.subject_name
            FROM edu.user_exam ue
            JOIN edu.exam    e USING (exam_id)
            JOIN edu.subject s USING (subject_id)
            WHERE ue.user_id = :uid
            ORDER BY e.exam_date
            """,
            {"uid": user_id},
        )

    # ── KPI aggregates ────────────────────────────────────────────────────────

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_academic_kpis(_self, start: date, end: date) -> dict:
        row = _self._read(
            """
            SELECT
                ROUND(AVG(sc.score::NUMERIC / NULLIF(sc.max_score,0) * 100), 2) AS avg_score_pct,
                ROUND(SUM(sc.is_passed::INT)::NUMERIC / NULLIF(COUNT(*),0) * 100, 2) AS pass_rate,
                COUNT(*) FILTER (WHERE sc.is_passed = FALSE) AS failed_count
            FROM edu.score sc
            WHERE sc.score_date BETWEEN :s AND :e
            """,
            {"s": start, "e": end},
        )
        att = _self._read(
            """
            SELECT ROUND(SUM(is_present::INT)::NUMERIC / NULLIF(COUNT(*),0) * 100, 2) AS avg_att
            FROM edu.attendance
            WHERE lesson_date BETWEEN :s AND :e
            """,
            {"s": start, "e": end},
        )
        active = _self._read(
            "SELECT COUNT(*) AS cnt FROM edu.\"user\" WHERE status = 'Обучается'"
        )
        result = row.iloc[0].to_dict() if not row.empty else {}
        result["avg_attendance"] = att.iloc[0]["avg_att"] if not att.empty else 0.0
        result["active_students"] = int(active.iloc[0]["cnt"]) if not active.empty else 0
        return result

    # ── At-risk students ──────────────────────────────────────────────────────

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_at_risk_students(_self) -> pd.DataFrame:
        """Students with avg score_pct < 60 or attendance_pct < 50."""
        return _self._read(
            """
            WITH score_agg AS (
                SELECT user_id,
                       ROUND(AVG(score::NUMERIC/NULLIF(max_score,0)*100),2) AS avg_score_pct
                FROM edu.score GROUP BY user_id
            ),
            att_agg AS (
                SELECT user_id,
                       ROUND(SUM(is_present::INT)::NUMERIC/NULLIF(COUNT(*),0)*100,2) AS att_pct
                FROM edu.attendance GROUP BY user_id
            )
            SELECT u.user_id, u.user_nickname, u.first_name, u.surname,
                   u.status, u.current_course,
                   COALESCE(sa.avg_score_pct, 0) AS avg_score_pct,
                   COALESCE(aa.att_pct, 0)       AS att_pct,
                   f.faculty_name, sg.group_name
            FROM edu."user" u
            LEFT JOIN score_agg sa ON sa.user_id = u.user_id
            LEFT JOIN att_agg   aa ON aa.user_id = u.user_id
            LEFT JOIN edu.user_study_group usg ON usg.user_id = u.user_id
            LEFT JOIN edu.study_group sg        ON sg.group_id = usg.group_id
            LEFT JOIN edu.program     p         ON p.program_id = sg.program_id
            LEFT JOIN edu.department  d         ON d.department_id = p.department_id
            LEFT JOIN edu.faculty     f         ON f.faculty_id = d.faculty_id
            WHERE u.status = 'Обучается'
              AND (COALESCE(sa.avg_score_pct, 0) < 60 OR COALESCE(aa.att_pct, 0) < 50)
            ORDER BY avg_score_pct
            """
        )

    # ── Score+attendance for correlation ─────────────────────────────────────

    @st.cache_data(ttl=get_ttl(), show_spinner=False)
    def get_per_user_academic_summary(_self, start: date, end: date) -> pd.DataFrame:
        return _self._read(
            """
            SELECT u.user_id,
                   ROUND(AVG(sc.score::NUMERIC/NULLIF(sc.max_score,0)*100),2) AS avg_score_pct,
                   ROUND(SUM(a.is_present::INT)::NUMERIC/NULLIF(COUNT(a.attendance_id),0)*100,2) AS att_pct
            FROM edu."user" u
            LEFT JOIN edu.score      sc ON sc.user_id = u.user_id
                   AND sc.score_date BETWEEN :s AND :e
            LEFT JOIN edu.attendance a  ON a.user_id  = u.user_id
                   AND a.lesson_date BETWEEN :s AND :e
            WHERE u.status = 'Обучается'
            GROUP BY u.user_id
            HAVING COUNT(sc.score_id) > 0
            """,
            {"s": start, "e": end},
        )
