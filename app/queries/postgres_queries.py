"""PostgreSQL запросы — временны́е ряды академических данных."""
from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine


def _q(engine: Engine, sql: str, params: dict | None = None) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


# ── Справочники ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=600, show_spinner=False)
def get_faculties(_engine: Engine) -> pd.DataFrame:
    return _q(_engine, "SELECT faculty_id, faculty_name FROM edu.faculty ORDER BY faculty_name")


@st.cache_data(ttl=600, show_spinner=False)
def get_subjects(_engine: Engine) -> pd.DataFrame:
    return _q(_engine, "SELECT subject_id, subject_name, semester FROM edu.subject ORDER BY subject_name")


@st.cache_data(ttl=600, show_spinner=False)
def get_semesters(_engine: Engine) -> pd.DataFrame:
    return _q(_engine, "SELECT DISTINCT semester FROM edu.subject WHERE semester IS NOT NULL ORDER BY semester")


@st.cache_data(ttl=600, show_spinner=False)
def get_courses(_engine: Engine) -> pd.DataFrame:
    return _q(_engine, "SELECT DISTINCT course FROM edu.study_group WHERE course IS NOT NULL ORDER BY course")


@st.cache_data(ttl=600, show_spinner=False)
def get_study_groups(_engine: Engine) -> pd.DataFrame:
    return _q(
        _engine,
        """
        SELECT DISTINCT ON (sg.group_name) sg.group_id, sg.group_name,
               sg.enrollment_year, sg.course, f.faculty_id, f.faculty_name
        FROM edu.study_group sg
        JOIN edu.program p    USING (program_id)
        JOIN edu.department d USING (department_id)
        JOIN edu.faculty f    USING (faculty_id)
        ORDER BY sg.group_name
        """,
    )


# ── GPA (средний балл) ────────────────────────────────────────────────────────

def _group_join_where(
    alias: str,
    where: str,
    params: dict,
    faculty_id: Optional[int] = None,
    group_id: Optional[int] = None,
) -> tuple[str, str]:
    """Возвращает (join_sql, where_sql) с фильтрами по факультету / группе."""
    join = ""
    if faculty_id or group_id:
        join = f"""
            JOIN edu.user_study_group _usg ON _usg.user_id = {alias}.user_id
            JOIN edu.study_group      _sg  ON _sg.group_id  = _usg.group_id
        """
    if faculty_id:
        join += """
            JOIN edu.program     _p  ON _p.program_id    = _sg.program_id
            JOIN edu.department  _d  ON _d.department_id = _p.department_id
        """
        where += " AND _d.faculty_id = :fid"
        params["fid"] = faculty_id
    if group_id:
        where += " AND _usg.group_id = :gid"
        params["gid"] = group_id
    return join, where


@st.cache_data(ttl=300, show_spinner=False)
def daily_gpa(
    _engine: Engine,
    start: date,
    end: date,
    faculty_id: Optional[int] = None,
    group_id: Optional[int] = None,
) -> pd.DataFrame:
    """Дневной средний балл (в % от max_score)."""
    where = "sc.score_date BETWEEN :s AND :e"
    params: dict = {"s": start, "e": end}
    join, where = _group_join_where("sc", where, params, faculty_id, group_id)
    return _q(
        _engine,
        f"""
        SELECT sc.score_date AS date,
               ROUND(AVG(sc.score::NUMERIC / NULLIF(sc.max_score,0) * 100), 2) AS avg_score_pct,
               COUNT(*) AS score_count
        FROM edu.score sc {join}
        WHERE {where}
        GROUP BY sc.score_date
        ORDER BY sc.score_date
        """,
        params,
    )


@st.cache_data(ttl=300, show_spinner=False)
def daily_gpa_by_cohort(
    _engine: Engine,
    start: date,
    end: date,
) -> pd.DataFrame:
    """Дневной средний балл (сырые баллы) по когортам (год поступления)."""
    return _q(
        _engine,
        """
        SELECT sc.score_date AS date,
               u.enrollment_year,
               ROUND(AVG(sc.score::NUMERIC), 2) AS avg_score,
               COUNT(*) AS score_count
        FROM edu.score sc
        JOIN edu."user" u ON u.user_id = sc.user_id
        WHERE sc.score_date BETWEEN :s AND :e
          AND u.enrollment_year BETWEEN 2021 AND 2024
        GROUP BY sc.score_date, u.enrollment_year
        ORDER BY sc.score_date, u.enrollment_year
        """,
        {"s": start, "e": end},
    )


@st.cache_data(ttl=300, show_spinner=False)
def daily_score_raw(
    _engine: Engine,
    start: date,
    end: date,
    faculty_id: Optional[int] = None,
    group_id: Optional[int] = None,
) -> pd.DataFrame:
    """Дневной: avg_score (сырые баллы), avg_max_score, кол-во студентов."""
    where = "sc.score_date BETWEEN :s AND :e"
    params: dict = {"s": start, "e": end}
    join, where = _group_join_where("sc", where, params, faculty_id, group_id)
    return _q(
        _engine,
        f"""
        SELECT sc.score_date AS date,
               ROUND(AVG(sc.score::NUMERIC), 2)     AS avg_score,
               ROUND(AVG(sc.max_score::NUMERIC), 2) AS avg_max_score,
               COUNT(DISTINCT sc.user_id)           AS student_count
        FROM edu.score sc {join}
        WHERE {where}
        GROUP BY sc.score_date
        ORDER BY sc.score_date
        """,
        params,
    )


@st.cache_data(ttl=300, show_spinner=False)
def weekly_score_distribution(
    _engine: Engine,
    start: date,
    end: date,
    group_id: Optional[int] = None,
) -> pd.DataFrame:
    """Распределение баллов (%) по неделям для boxplot."""
    where = "sc.score_date BETWEEN :s AND :e"
    params: dict = {"s": start, "e": end}
    join = ""
    if group_id:
        join = "JOIN edu.user_study_group _usg ON _usg.user_id = sc.user_id"
        where += " AND _usg.group_id = :gid"
        params["gid"] = group_id
    return _q(
        _engine,
        f"""
        SELECT DATE_TRUNC('week', sc.score_date)::DATE AS week,
               ROUND(PERCENTILE_CONT(0.0)  WITHIN GROUP
                     (ORDER BY sc.score::FLOAT / NULLIF(sc.max_score,0) * 100)::NUMERIC, 1) AS q0,
               ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP
                     (ORDER BY sc.score::FLOAT / NULLIF(sc.max_score,0) * 100)::NUMERIC, 1) AS q25,
               ROUND(PERCENTILE_CONT(0.5)  WITHIN GROUP
                     (ORDER BY sc.score::FLOAT / NULLIF(sc.max_score,0) * 100)::NUMERIC, 1) AS q50,
               ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP
                     (ORDER BY sc.score::FLOAT / NULLIF(sc.max_score,0) * 100)::NUMERIC, 1) AS q75,
               ROUND(PERCENTILE_CONT(1.0)  WITHIN GROUP
                     (ORDER BY sc.score::FLOAT / NULLIF(sc.max_score,0) * 100)::NUMERIC, 1) AS q100,
               COUNT(*) AS score_count
        FROM edu.score sc {join}
        WHERE {where}
        GROUP BY week
        ORDER BY week
        """,
        params,
    )


@st.cache_data(ttl=300, show_spinner=False)
def monthly_subject_scores(
    _engine: Engine,
    start: date,
    end: date,
    top_n: int = 25,
) -> pd.DataFrame:
    """Средний балл по предметам помесячно — для heatmap."""
    return _q(
        _engine,
        """
        WITH top_subjects AS (
            SELECT subject_id
            FROM edu.score
            WHERE score_date BETWEEN :s AND :e
            GROUP BY subject_id
            ORDER BY COUNT(*) DESC
            LIMIT :n
        )
        SELECT s.subject_name,
               DATE_TRUNC('month', sc.score_date)::DATE AS month,
               ROUND(AVG(sc.score::NUMERIC / NULLIF(sc.max_score,0) * 100), 1) AS avg_score_pct,
               COUNT(*) AS score_count
        FROM edu.score sc
        JOIN edu.subject s ON s.subject_id = sc.subject_id
        JOIN top_subjects ts ON ts.subject_id = sc.subject_id
        WHERE sc.score_date BETWEEN :s AND :e
        GROUP BY s.subject_name, month
        ORDER BY month, s.subject_name
        """,
        {"s": start, "e": end, "n": top_n},
    )


# ── Посещаемость ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def daily_attendance(
    _engine: Engine,
    start: date,
    end: date,
    faculty_id: Optional[int] = None,
    group_id: Optional[int] = None,
) -> pd.DataFrame:
    """Дневной процент посещаемости."""
    where = "a.lesson_date BETWEEN :s AND :e"
    params: dict = {"s": start, "e": end}
    join, where = _group_join_where("a", where, params, faculty_id, group_id)
    return _q(
        _engine,
        f"""
        SELECT a.lesson_date AS date,
               ROUND(SUM(a.is_present::INT)::NUMERIC / NULLIF(COUNT(*),0) * 100, 2) AS attendance_pct,
               COUNT(*) AS total_lessons
        FROM edu.attendance a {join}
        WHERE {where}
        GROUP BY a.lesson_date
        ORDER BY a.lesson_date
        """,
        params,
    )


# ── Pass rate ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def daily_pass_rate(
    _engine: Engine,
    start: date,
    end: date,
    group_id: Optional[int] = None,
) -> pd.DataFrame:
    """Дневной процент успешных сдач."""
    where = "sc.score_date BETWEEN :s AND :e"
    params: dict = {"s": start, "e": end}
    join = ""
    if group_id:
        join = "JOIN edu.user_study_group _usg ON _usg.user_id = sc.user_id"
        where += " AND _usg.group_id = :gid"
        params["gid"] = group_id
    return _q(
        _engine,
        f"""
        SELECT sc.score_date AS date,
               ROUND(SUM(sc.is_passed::INT)::NUMERIC / NULLIF(COUNT(*),0) * 100, 2) AS pass_rate,
               COUNT(*) AS total
        FROM edu.score sc {join}
        WHERE {where}
        GROUP BY sc.score_date
        ORDER BY sc.score_date
        """,
        params,
    )


# ── Per-user academic summary (для корреляции) ────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def per_user_academic(
    _engine: Engine,
    start: date,
    end: date,
) -> pd.DataFrame:
    """Средний балл и посещаемость по каждому студенту за период."""
    return _q(
        _engine,
        """
        SELECT u.user_id,
               ROUND(AVG(sc.score::NUMERIC/NULLIF(sc.max_score,0)*100), 2) AS avg_score_pct,
               ROUND(SUM(a.is_present::INT)::NUMERIC/NULLIF(COUNT(DISTINCT a.attendance_id),0)*100, 2) AS att_pct
        FROM edu."user" u
        LEFT JOIN edu.score      sc ON sc.user_id = u.user_id
               AND sc.score_date BETWEEN :s AND :e
        LEFT JOIN edu.attendance a  ON a.user_id  = u.user_id
               AND a.lesson_date BETWEEN :s AND :e
        WHERE u.status = 'Обучается'
        GROUP BY u.user_id
        HAVING COUNT(sc.score_id) > 2
        """,
        {"s": start, "e": end},
    )


# ── Поиск и профиль студента ──────────────────────────────────────────────────

@st.cache_data(ttl=120, show_spinner=False)
def search_users(_engine: Engine, query: str, limit: int = 30) -> pd.DataFrame:
    """Поиск студентов по никнейму, фамилии или имени."""
    q = f"%{query.strip().lower()}%"
    return _q(
        _engine,
        """
        SELECT DISTINCT ON (u.user_id)
               u.user_id,
               u.user_nickname,
               u.first_name,
               u.surname,
               u.middle_name,
               u.current_course,
               u.status,
               u.enrollment_year,
               sg.group_name,
               f.faculty_name
        FROM edu."user" u
        LEFT JOIN edu.user_study_group usg ON usg.user_id = u.user_id
        LEFT JOIN edu.study_group sg       ON sg.group_id  = usg.group_id
        LEFT JOIN edu.program p            ON p.program_id = sg.program_id
        LEFT JOIN edu.department d         ON d.department_id = p.department_id
        LEFT JOIN edu.faculty f            ON f.faculty_id = d.faculty_id
        WHERE LOWER(u.user_nickname) LIKE :q
           OR LOWER(u.surname)       LIKE :q
           OR LOWER(u.first_name)    LIKE :q
        ORDER BY u.user_id, u.surname, u.first_name
        LIMIT :lim
        """,
        {"q": q, "lim": limit},
    )


@st.cache_data(ttl=120, show_spinner=False)
def user_score_timeline(_engine: Engine, user_id: int) -> pd.DataFrame:
    """История оценок студента по дням."""
    return _q(
        _engine,
        """
        SELECT sc.score_date AS date,
               s.subject_name,
               sc.score,
               sc.max_score,
               ROUND(sc.score::NUMERIC / NULLIF(sc.max_score,0) * 100, 1) AS score_pct,
               sc.score_type,
               sc.is_passed
        FROM edu.score sc
        JOIN edu.subject s ON s.subject_id = sc.subject_id
        WHERE sc.user_id = :uid
        ORDER BY sc.score_date, s.subject_name
        """,
        {"uid": user_id},
    )


@st.cache_data(ttl=120, show_spinner=False)
def user_subject_summary(_engine: Engine, user_id: int) -> pd.DataFrame:
    """Итоги по предметам: средний балл, посещаемость, число сдач."""
    return _q(
        _engine,
        """
        SELECT s.subject_name,
               ROUND(AVG(sc.score::NUMERIC / NULLIF(sc.max_score,0) * 100), 1) AS avg_score_pct,
               ROUND(AVG(sc.score::NUMERIC), 1)                                  AS avg_score,
               COUNT(sc.score_id)                                                 AS attempts,
               SUM(sc.is_passed::INT)                                             AS passed,
               ROUND(
                   SUM(a.is_present::INT)::NUMERIC /
                   NULLIF(COUNT(DISTINCT a.attendance_id), 0) * 100, 1
               )                                                                  AS att_pct
        FROM edu.subject s
        LEFT JOIN edu.score sc      ON sc.subject_id = s.subject_id AND sc.user_id = :uid
        LEFT JOIN edu.attendance a  ON a.subject_id  = s.subject_id AND a.user_id  = :uid
        WHERE sc.user_id = :uid OR a.user_id = :uid
        GROUP BY s.subject_name
        ORDER BY avg_score_pct DESC NULLS LAST
        """,
        {"uid": user_id},
    )


@st.cache_data(ttl=120, show_spinner=False)
def user_vs_avg_daily(_engine: Engine, user_id: int) -> pd.DataFrame:
    """Дневной балл студента vs средний по всем (для сравнения)."""
    return _q(
        _engine,
        """
        WITH user_daily AS (
            SELECT score_date AS date,
                   ROUND(AVG(score::NUMERIC / NULLIF(max_score,0) * 100), 2) AS user_pct,
                   ROUND(AVG(score::NUMERIC), 2)                              AS user_score
            FROM edu.score
            WHERE user_id = :uid
            GROUP BY score_date
        ),
        avg_daily AS (
            SELECT score_date AS date,
                   ROUND(AVG(score::NUMERIC / NULLIF(max_score,0) * 100), 2) AS avg_pct
            FROM edu.score
            GROUP BY score_date
        )
        SELECT u.date, u.user_pct, u.user_score, a.avg_pct
        FROM user_daily u
        LEFT JOIN avg_daily a USING (date)
        ORDER BY u.date
        """,
        {"uid": user_id},
    )


# ── Новые запросы для академической аналитики ─────────────────────────────────

def _build_scope_joins(
    alias: str,
    where: str,
    params: dict,
    student_id: Optional[int] = None,
    group_id: Optional[int] = None,
    faculty_id: Optional[int] = None,
    course: Optional[int] = None,
) -> tuple[str, str]:
    """Builds JOIN+WHERE clauses for scope filters."""
    if student_id:
        where += f" AND {alias}.user_id = :uid"
        params["uid"] = student_id

    need_sg = group_id or faculty_id or course
    joins = ""
    if need_sg:
        joins += f"""
            JOIN edu.user_study_group _usg2 ON _usg2.user_id = {alias}.user_id
            JOIN edu.study_group      _sg2  ON _sg2.group_id  = _usg2.group_id
        """
        if group_id:
            where += " AND _usg2.group_id = :gid2"
            params["gid2"] = group_id
        if course:
            where += " AND _sg2.course = :course2"
            params["course2"] = course
        if faculty_id:
            joins += """
                JOIN edu.program    _p2 ON _p2.program_id    = _sg2.program_id
                JOIN edu.department _d2 ON _d2.department_id = _p2.department_id
            """
            where += " AND _d2.faculty_id = :fid2"
            params["fid2"] = faculty_id
    return joins, where


@st.cache_data(ttl=300, show_spinner=False)
def load_scores_for_level(
    _engine: Engine,
    start: date,
    end: date,
    student_id: Optional[int] = None,
    group_id: Optional[int] = None,
    faculty_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    semester: Optional[int] = None,
    course: Optional[int] = None,
) -> pd.DataFrame:
    """Raw score rows for given scope."""
    where = "sc.score_date BETWEEN :s AND :e"
    params: dict = {"s": start, "e": end}
    joins, where = _build_scope_joins("sc", where, params, student_id, group_id, faculty_id, course)

    if subject_id:
        where += " AND sc.subject_id = :subj"
        params["subj"] = subject_id
    if semester:
        joins += " JOIN edu.subject _sem_s ON _sem_s.subject_id = sc.subject_id"
        where += " AND _sem_s.semester = :sem"
        params["sem"] = semester

    return _q(
        _engine,
        f"""
        SELECT sc.user_id,
               sc.score_date         AS date,
               sc.score::NUMERIC     AS score,
               sc.max_score::NUMERIC AS max_score,
               sc.is_passed::INT     AS is_passed,
               sc.subject_id
        FROM edu.score sc {joins}
        WHERE {where}
        ORDER BY sc.score_date, sc.user_id
        """,
        params,
    )


@st.cache_data(ttl=300, show_spinner=False)
def load_attendance_for_level(
    _engine: Engine,
    start: date,
    end: date,
    student_id: Optional[int] = None,
    group_id: Optional[int] = None,
    faculty_id: Optional[int] = None,
    course: Optional[int] = None,
) -> pd.DataFrame:
    """Raw attendance rows for given scope."""
    where = "a.lesson_date BETWEEN :s AND :e"
    params: dict = {"s": start, "e": end}
    joins, where = _build_scope_joins("a", where, params, student_id, group_id, faculty_id, course)

    return _q(
        _engine,
        f"""
        SELECT a.user_id,
               a.lesson_date       AS date,
               a.is_present::INT   AS is_present,
               a.subject_id
        FROM edu.attendance a {joins}
        WHERE {where}
        ORDER BY a.lesson_date, a.user_id
        """,
        params,
    )


@st.cache_data(ttl=300, show_spinner=False)
def summary_table_student(_engine: Engine, student_id: int, start: date, end: date) -> pd.DataFrame:
    return _q(
        _engine,
        """
        SELECT sub.subject_name,
               COALESCE(ROUND(SUM(sc.score::NUMERIC), 1), 0)     AS scored,
               COALESCE(ROUND(SUM(sc.max_score::NUMERIC), 1), 0) AS available,
               CASE WHEN SUM(sc.max_score::NUMERIC) > 0
                    THEN ROUND(SUM(sc.score::NUMERIC) /
                               SUM(sc.max_score::NUMERIC) * 100, 1)
                    ELSE NULL END                                  AS progress_pct,
               ROUND(SUM(a.is_present::INT)::NUMERIC /
                     NULLIF(COUNT(DISTINCT a.attendance_id), 0) * 100, 1) AS att_pct
        FROM edu.subject sub
        LEFT JOIN edu.score sc
               ON sc.subject_id = sub.subject_id
              AND sc.user_id     = :uid
              AND sc.score_date BETWEEN :s AND :e
        LEFT JOIN edu.attendance a
               ON a.subject_id  = sub.subject_id
              AND a.user_id      = :uid
              AND a.lesson_date BETWEEN :s AND :e
        WHERE sc.user_id = :uid OR a.user_id = :uid
        GROUP BY sub.subject_id, sub.subject_name
        ORDER BY progress_pct ASC NULLS LAST
        """,
        {"uid": student_id, "s": start, "e": end},
    )


@st.cache_data(ttl=300, show_spinner=False)
def summary_table_group(_engine: Engine, group_id: int, start: date, end: date) -> pd.DataFrame:
    return _q(
        _engine,
        """
        WITH sc_stats AS (
            SELECT sc.user_id,
                   SUM(sc.score::NUMERIC)     AS total_score,
                   SUM(sc.max_score::NUMERIC) AS total_max,
                   ROUND(SUM(sc.is_passed::INT)::NUMERIC /
                         NULLIF(COUNT(*), 0) * 100, 1)  AS pass_rate
            FROM edu.score sc
            JOIN edu.user_study_group usg ON usg.user_id = sc.user_id AND usg.group_id = :gid
            WHERE sc.score_date BETWEEN :s AND :e
            GROUP BY sc.user_id
        ),
        att_stats AS (
            SELECT a.user_id,
                   ROUND(SUM(a.is_present::INT)::NUMERIC /
                         NULLIF(COUNT(*), 0) * 100, 1)  AS att_pct
            FROM edu.attendance a
            JOIN edu.user_study_group usg ON usg.user_id = a.user_id AND usg.group_id = :gid
            WHERE a.lesson_date BETWEEN :s AND :e
            GROUP BY a.user_id
        )
        SELECT u.user_id,
               u.surname || ' ' || u.first_name AS student_name,
               CASE WHEN sc.total_max > 0
                    THEN ROUND(sc.total_score / sc.total_max * 100, 1)
                    ELSE NULL END                AS progress_pct,
               att.att_pct,
               sc.pass_rate
        FROM edu."user" u
        JOIN edu.user_study_group usg ON usg.user_id = u.user_id AND usg.group_id = :gid
        LEFT JOIN sc_stats  sc  ON sc.user_id  = u.user_id
        LEFT JOIN att_stats att ON att.user_id = u.user_id
        ORDER BY progress_pct ASC NULLS LAST
        """,
        {"gid": group_id, "s": start, "e": end},
    )


@st.cache_data(ttl=300, show_spinner=False)
def summary_table_faculty(_engine: Engine, faculty_id: int, start: date, end: date) -> pd.DataFrame:
    return _q(
        _engine,
        """
        WITH stu AS (
            SELECT usg.group_id, sc.user_id,
                   CASE WHEN SUM(sc.max_score::NUMERIC) > 0
                        THEN SUM(sc.score::NUMERIC) / SUM(sc.max_score::NUMERIC) * 100
                        ELSE NULL END AS progress_pct,
                   SUM(sc.is_passed::INT)::FLOAT / NULLIF(COUNT(*), 0) * 100 AS pass_rate
            FROM edu.score sc
            JOIN edu.user_study_group usg ON usg.user_id = sc.user_id
            JOIN edu.study_group      sg  ON sg.group_id  = usg.group_id
            JOIN edu.program          p   ON p.program_id = sg.program_id
            JOIN edu.department       d   ON d.department_id = p.department_id
            WHERE d.faculty_id = :fid AND sc.score_date BETWEEN :s AND :e
            GROUP BY usg.group_id, sc.user_id
        ),
        att AS (
            SELECT usg.group_id, a.user_id,
                   SUM(a.is_present::INT)::FLOAT / NULLIF(COUNT(*), 0) * 100 AS att_pct
            FROM edu.attendance a
            JOIN edu.user_study_group usg ON usg.user_id = a.user_id
            JOIN edu.study_group      sg  ON sg.group_id  = usg.group_id
            JOIN edu.program          p   ON p.program_id = sg.program_id
            JOIN edu.department       d   ON d.department_id = p.department_id
            WHERE d.faculty_id = :fid AND a.lesson_date BETWEEN :s AND :e
            GROUP BY usg.group_id, a.user_id
        )
        SELECT sg.group_name,
               ROUND(AVG(s.progress_pct)::NUMERIC, 1) AS avg_progress,
               ROUND(AVG(a.att_pct)::NUMERIC, 1)       AS avg_att,
               ROUND(AVG(s.pass_rate)::NUMERIC, 1)     AS pass_rate,
               ROUND(COUNT(CASE WHEN s.progress_pct < 60 THEN 1 END)::NUMERIC
                     / NULLIF(COUNT(s.user_id), 0) * 100, 1) AS risk_share
        FROM edu.study_group sg
        JOIN edu.program     p ON p.program_id    = sg.program_id
        JOIN edu.department  d ON d.department_id = p.department_id
        LEFT JOIN stu s ON s.group_id = sg.group_id
        LEFT JOIN att a ON a.group_id = sg.group_id AND a.user_id = s.user_id
        WHERE d.faculty_id = :fid
        GROUP BY sg.group_id, sg.group_name
        ORDER BY avg_progress ASC NULLS LAST
        """,
        {"fid": faculty_id, "s": start, "e": end},
    )


@st.cache_data(ttl=300, show_spinner=False)
def summary_table_all(_engine: Engine, start: date, end: date) -> pd.DataFrame:
    return _q(
        _engine,
        """
        WITH stu AS (
            SELECT d.faculty_id, sc.user_id,
                   CASE WHEN SUM(sc.max_score::NUMERIC) > 0
                        THEN SUM(sc.score::NUMERIC) / SUM(sc.max_score::NUMERIC) * 100
                        ELSE NULL END AS progress_pct,
                   SUM(sc.is_passed::INT)::FLOAT / NULLIF(COUNT(*), 0) * 100 AS pass_rate
            FROM edu.score sc
            JOIN edu.user_study_group usg ON usg.user_id = sc.user_id
            JOIN edu.study_group      sg  ON sg.group_id  = usg.group_id
            JOIN edu.program          p   ON p.program_id = sg.program_id
            JOIN edu.department       d   ON d.department_id = p.department_id
            WHERE sc.score_date BETWEEN :s AND :e
            GROUP BY d.faculty_id, sc.user_id
        ),
        att AS (
            SELECT d.faculty_id, a.user_id,
                   SUM(a.is_present::INT)::FLOAT / NULLIF(COUNT(*), 0) * 100 AS att_pct
            FROM edu.attendance a
            JOIN edu.user_study_group usg ON usg.user_id = a.user_id
            JOIN edu.study_group      sg  ON sg.group_id  = usg.group_id
            JOIN edu.program          p   ON p.program_id = sg.program_id
            JOIN edu.department       d   ON d.department_id = p.department_id
            WHERE a.lesson_date BETWEEN :s AND :e
            GROUP BY d.faculty_id, a.user_id
        )
        SELECT f.faculty_name,
               ROUND(AVG(s.progress_pct)::NUMERIC, 1) AS avg_progress,
               ROUND(AVG(a.att_pct)::NUMERIC, 1)       AS avg_att,
               ROUND(AVG(s.pass_rate)::NUMERIC, 1)     AS pass_rate,
               ROUND(COUNT(CASE WHEN s.progress_pct < 60 THEN 1 END)::NUMERIC
                     / NULLIF(COUNT(s.user_id), 0) * 100, 1) AS risk_share
        FROM edu.faculty f
        LEFT JOIN stu s ON s.faculty_id = f.faculty_id
        LEFT JOIN att a ON a.faculty_id = f.faculty_id AND a.user_id = s.user_id
        GROUP BY f.faculty_id, f.faculty_name
        ORDER BY avg_progress ASC NULLS LAST
        """,
        {"s": start, "e": end},
    )


@st.cache_data(ttl=600, show_spinner=False)
def subject_names(_engine: Engine) -> pd.DataFrame:
    return _q(_engine, "SELECT subject_id, subject_name FROM edu.subject")


# ── Расширенные запросы для корреляционной аналитики ─────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def users_for_scope(
    _engine: Engine,
    group_id: Optional[int] = None,
    faculty_id: Optional[int] = None,
    course: Optional[int] = None,
) -> list[int]:
    """Returns user_id list for given group/faculty/course scope."""
    if not group_id and not faculty_id and not course:
        return []

    where = "1=1"
    params: dict = {}

    joins = """
        JOIN edu.user_study_group usg ON usg.user_id = u.user_id
        JOIN edu.study_group sg ON sg.group_id = usg.group_id
    """
    if group_id:
        where += " AND usg.group_id = :gid"
        params["gid"] = group_id
    if course:
        where += " AND sg.course = :course"
        params["course"] = course
    if faculty_id:
        joins += """
            JOIN edu.program p ON p.program_id = sg.program_id
            JOIN edu.department d ON d.department_id = p.department_id
        """
        where += " AND d.faculty_id = :fid"
        params["fid"] = faculty_id

    df = _q(_engine, f"""
        SELECT DISTINCT u.user_id
        FROM edu."user" u {joins}
        WHERE {where}
    """, params)
    return df["user_id"].tolist() if not df.empty else []


@st.cache_data(ttl=300, show_spinner=False)
def per_user_academic_extended(
    _engine: Engine,
    start: date,
    end: date,
    group_id: Optional[int] = None,
    faculty_id: Optional[int] = None,
    course: Optional[int] = None,
) -> pd.DataFrame:
    """Per-user: progress_pct, weekly_points, attendance_pct, pass_rate, risk_flag."""
    where = "sc.score_date BETWEEN :s AND :e"
    params: dict = {"s": start, "e": end}
    joins, where = _build_scope_joins("sc", where, params, None, group_id, faculty_id, course)

    scores_df = _q(
        _engine,
        f"""
        SELECT sc.user_id,
               SUM(sc.score::NUMERIC)     AS total_score,
               SUM(sc.max_score::NUMERIC) AS total_max,
               ROUND(SUM(sc.is_passed::INT)::NUMERIC / NULLIF(COUNT(*),0)*100,1) AS pass_rate
        FROM edu.score sc {joins}
        WHERE {where}
        GROUP BY sc.user_id
        HAVING SUM(sc.max_score::NUMERIC) > 0
        """,
        params,
    )
    if scores_df.empty:
        return pd.DataFrame()

    # attendance — same scope
    att_where = "a.lesson_date BETWEEN :s AND :e"
    att_params: dict = {"s": start, "e": end}
    att_joins, att_where = _build_scope_joins("a", att_where, att_params, None, group_id, faculty_id, course)
    att_df = _q(
        _engine,
        f"""
        SELECT a.user_id,
               ROUND(SUM(a.is_present::INT)::NUMERIC / NULLIF(COUNT(*),0)*100,1) AS att_pct
        FROM edu.attendance a {att_joins}
        WHERE {att_where}
        GROUP BY a.user_id
        """,
        att_params,
    )

    df = scores_df.merge(att_df, on="user_id", how="left")
    df["progress_pct"] = (df["total_score"] / df["total_max"] * 100).round(1)
    df["risk_flag"]    = (df["progress_pct"] < 60).astype(int)
    return df.reset_index(drop=True)


@st.cache_data(ttl=300, show_spinner=False)
def per_user_weekly_academic(
    _engine: Engine,
    start: date,
    end: date,
    group_id: Optional[int] = None,
    faculty_id: Optional[int] = None,
) -> pd.DataFrame:
    """Per-user per-week: weekly_score, weekly_max, pass_rate."""
    where = "sc.score_date BETWEEN :s AND :e"
    params: dict = {"s": start, "e": end}
    joins, where = _build_scope_joins("sc", where, params, None, group_id, faculty_id, None)

    return _q(
        _engine,
        f"""
        SELECT sc.user_id,
               DATE_TRUNC('week', sc.score_date)::DATE  AS week,
               SUM(sc.score::NUMERIC)                    AS weekly_score,
               SUM(sc.max_score::NUMERIC)                AS weekly_max,
               ROUND(SUM(sc.is_passed::INT)::NUMERIC /
                     NULLIF(COUNT(*),0)*100, 1)          AS pass_rate
        FROM edu.score sc {joins}
        WHERE {where}
        GROUP BY sc.user_id, week
        ORDER BY sc.user_id, week
        """,
        params,
    )


@st.cache_data(ttl=300, show_spinner=False)
def weekly_academic_agg(
    _engine: Engine,
    start: date,
    end: date,
    group_id: Optional[int] = None,
    faculty_id: Optional[int] = None,
) -> pd.DataFrame:
    """Weekly aggregate: avg score, attendance, pass_rate (for time-series corr)."""
    where_sc = "sc.score_date BETWEEN :s AND :e"
    params: dict = {"s": start, "e": end}
    joins_sc, where_sc = _build_scope_joins("sc", where_sc, params, None, group_id, faculty_id, None)

    scores = _q(_engine, f"""
        SELECT DATE_TRUNC('week', sc.score_date)::DATE AS week,
               ROUND(AVG(sc.score::NUMERIC / NULLIF(sc.max_score,0)*100),2) AS avg_score_pct,
               ROUND(SUM(sc.is_passed::INT)::NUMERIC / NULLIF(COUNT(*),0)*100,2) AS pass_rate
        FROM edu.score sc {joins_sc}
        WHERE {where_sc}
        GROUP BY week
        ORDER BY week
    """, params)

    att_where = "a.lesson_date BETWEEN :sa AND :ea"
    att_params: dict = {"sa": start, "ea": end}
    joins_att, att_where = _build_scope_joins("a", att_where, att_params, None, group_id, faculty_id, None)

    att = _q(_engine, f"""
        SELECT DATE_TRUNC('week', a.lesson_date)::DATE AS week,
               ROUND(SUM(a.is_present::INT)::NUMERIC / NULLIF(COUNT(*),0)*100,2) AS attendance_pct
        FROM edu.attendance a {joins_att}
        WHERE {att_where}
        GROUP BY week
        ORDER BY week
    """, att_params)

    if scores.empty:
        return pd.DataFrame()
    return scores.merge(att, on="week", how="left").sort_values("week").reset_index(drop=True)
