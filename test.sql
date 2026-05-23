-- =============================================================================
-- test.sql — проверочные SELECT по каждой таблице схемы edu
-- =============================================================================

SET search_path = edu;

-- ---------------------------------------------------------------------------
\echo '=== education_degree ==='
SELECT * FROM edu.education_degree;

-- ---------------------------------------------------------------------------
\echo '=== education_form ==='
SELECT * FROM edu.education_form;

-- ---------------------------------------------------------------------------
\echo '=== faculty (10 rows) ==='
SELECT * FROM edu.faculty ORDER BY faculty_id;

-- ---------------------------------------------------------------------------
\echo '=== department (sample 10) ==='
SELECT * FROM edu.department ORDER BY department_id LIMIT 10;

-- ---------------------------------------------------------------------------
\echo '=== program (sample 10) ==='
SELECT
    p.program_id,
    p.education_code,
    d.degree_name,
    f.form_name,
    dep.department_name,
    p.year_of_study,
    p.speciality
FROM edu.program p
JOIN edu.education_degree d   ON d.degree_id     = p.degree_id
JOIN edu.education_form   f   ON f.form_id        = p.form_id
JOIN edu.department       dep ON dep.department_id = p.department_id
ORDER BY p.program_id
LIMIT 10;

-- ---------------------------------------------------------------------------
\echo '=== study_group (sample 10) ==='
SELECT
    sg.group_id,
    sg.group_name,
    sg.enrollment_year,
    sg.course,
    sg.semestr,
    p.speciality AS program
FROM edu.study_group sg
JOIN edu.program p ON p.program_id = sg.program_id
ORDER BY sg.group_id
LIMIT 10;

-- ---------------------------------------------------------------------------
\echo '=== user (sample 10) ==='
SELECT
    user_id,
    user_nickname,
    first_name,
    surname,
    gender,
    enrollment_year,
    funding_type,
    status,
    current_course
FROM edu."user"
ORDER BY user_id
LIMIT 10;

-- ---------------------------------------------------------------------------
\echo '=== user_study_group (sample 10) ==='
SELECT
    usg.user_id,
    u.user_nickname,
    usg.group_id,
    sg.group_name
FROM edu.user_study_group usg
JOIN edu."user"       u  ON u.user_id   = usg.user_id
JOIN edu.study_group sg  ON sg.group_id = usg.group_id
ORDER BY usg.user_id
LIMIT 10;

-- ---------------------------------------------------------------------------
\echo '=== subject (sample 10) ==='
SELECT * FROM edu.subject ORDER BY subject_id LIMIT 10;

-- ---------------------------------------------------------------------------
\echo '=== user_subject (sample 10) ==='
SELECT
    us.user_id,
    u.user_nickname,
    us.subject_id,
    s.subject_name
FROM edu.user_subject us
JOIN edu."user"   u ON u.user_id   = us.user_id
JOIN edu.subject  s ON s.subject_id = us.subject_id
ORDER BY us.user_id
LIMIT 10;

-- ---------------------------------------------------------------------------
\echo '=== exam (sample 10) ==='
SELECT
    e.exam_id,
    s.subject_name,
    e.exam_date,
    e.exam_time,
    e.exam_type,
    e.passed_type
FROM edu.exam e
JOIN edu.subject s ON s.subject_id = e.subject_id
ORDER BY e.exam_date
LIMIT 10;

-- ---------------------------------------------------------------------------
\echo '=== user_exam (sample 10) ==='
SELECT
    ue.user_id,
    u.user_nickname,
    ue.exam_id,
    s.subject_name,
    e.exam_date
FROM edu.user_exam ue
JOIN edu."user"  u ON u.user_id    = ue.user_id
JOIN edu.exam    e ON e.exam_id    = ue.exam_id
JOIN edu.subject s ON s.subject_id = e.subject_id
ORDER BY ue.user_id
LIMIT 10;

-- ---------------------------------------------------------------------------
\echo '=== page (sample 10) ==='
SELECT * FROM edu.page ORDER BY page_id LIMIT 10;

-- ---------------------------------------------------------------------------
\echo '=== score (sample 10) ==='
SELECT
    sc.score_id,
    u.user_nickname,
    s.subject_name,
    sc.score_date,
    sc.score_type,
    sc.score,
    sc.max_score,
    sc.attempt_number,
    sc.is_passed,
    sc.module
FROM edu.score sc
JOIN edu."user"  u ON u.user_id    = sc.user_id
JOIN edu.subject s ON s.subject_id = sc.subject_id
ORDER BY sc.score_id
LIMIT 10;

-- ---------------------------------------------------------------------------
\echo '=== attendance (sample 10) ==='
SELECT
    a.attendance_id,
    u.user_nickname,
    s.subject_name,
    a.lesson_date,
    a.lesson_time,
    a.lesson_type,
    a.is_present
FROM edu.attendance a
JOIN edu."user"  u ON u.user_id    = a.user_id
JOIN edu.subject s ON s.subject_id = a.subject_id
ORDER BY a.attendance_id
LIMIT 10;

-- ===========================================================================
-- ИТОГОВЫЕ СЧЁТЧИКИ ПО ВСЕМ ТАБЛИЦАМ
-- ===========================================================================
\echo '=== row counts per table ==='
SELECT
    relname                                  AS table_name,
    reltuples::BIGINT                        AS approx_rows
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'edu'
  AND c.relkind = 'r'
ORDER BY reltuples DESC;

-- ===========================================================================
-- БЫСТРАЯ АНАЛИТИЧЕСКАЯ ПРОВЕРКА
-- ===========================================================================

\echo '=== avg score % by faculty ==='
SELECT
    fac.faculty_name,
    COUNT(DISTINCT u.user_id)                                       AS students,
    ROUND(AVG(sc.score::NUMERIC / sc.max_score * 100), 2)          AS avg_score_pct,
    ROUND(
        SUM(a.is_present::INT)::NUMERIC /
        NULLIF(COUNT(a.attendance_id), 0) * 100, 2
    )                                                               AS avg_attendance_pct
FROM edu.faculty        fac
JOIN edu.department     dep ON dep.faculty_id    = fac.faculty_id
JOIN edu.program        p   ON p.department_id   = dep.department_id
JOIN edu.study_group    sg  ON sg.program_id     = p.program_id
JOIN edu.user_study_group usg ON usg.group_id   = sg.group_id
JOIN edu."user"         u   ON u.user_id         = usg.user_id
LEFT JOIN edu.score     sc  ON sc.user_id        = u.user_id
LEFT JOIN edu.attendance a  ON a.user_id         = u.user_id
GROUP BY fac.faculty_name
ORDER BY avg_score_pct DESC NULLS LAST;

\echo '=== student status distribution ==='
SELECT
    status,
    COUNT(*)                                              AS cnt,
    ROUND(COUNT(*)::NUMERIC / SUM(COUNT(*)) OVER () * 100, 1) AS pct
FROM edu."user"
GROUP BY status
ORDER BY cnt DESC;

\echo '=== pass rate by score_type ==='
SELECT
    score_type,
    COUNT(*)                                                           AS total,
    SUM(is_passed::INT)                                                AS passed,
    ROUND(SUM(is_passed::INT)::NUMERIC / COUNT(*) * 100, 1)           AS pass_rate_pct
FROM edu.score
GROUP BY score_type
ORDER BY total DESC;
