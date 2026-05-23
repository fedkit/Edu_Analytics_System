-- =============================================================================
-- PostgreSQL Views — Electronic University
-- Только бизнес/аналитические VIEW, без materialized views
-- =============================================================================

SET search_path = edu;

-- ---------------------------------------------------------------------------
-- 1. student_performance_view
--    Средний балл, количество предметов, прогресс по студенту
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW edu.student_performance_view AS
SELECT
    u.user_id,
    u.user_nickname,
    u.first_name,
    u.surname,
    u.current_course,
    u.status,
    COUNT(DISTINCT us.subject_id)                                        AS subject_count,
    COUNT(sc.score_id)                                                   AS total_scores,
    ROUND(
        AVG(sc.score::NUMERIC / NULLIF(sc.max_score, 0) * 100), 2
    )                                                                    AS avg_score_pct,
    COUNT(sc.score_id) FILTER (WHERE sc.is_passed = TRUE)               AS passed_count,
    COUNT(sc.score_id) FILTER (WHERE sc.is_passed = FALSE)              AS failed_count
FROM edu.user u
LEFT JOIN edu.user_subject us ON us.user_id   = u.user_id
LEFT JOIN edu.score        sc ON sc.user_id   = u.user_id
GROUP BY u.user_id, u.user_nickname, u.first_name, u.surname,
         u.current_course, u.status;

-- ---------------------------------------------------------------------------
-- 2. attendance_summary_view
--    Процент посещаемости по студенту и предмету
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW edu.attendance_summary_view AS
SELECT
    u.user_id,
    u.user_nickname,
    u.first_name,
    u.surname,
    s.subject_id,
    s.subject_name,
    s.semestr,
    a.lesson_type,
    COUNT(a.attendance_id)                                               AS total_lessons,
    SUM(a.is_present::INT)                                              AS attended,
    ROUND(
        SUM(a.is_present::INT)::NUMERIC /
        NULLIF(COUNT(a.attendance_id), 0) * 100, 2
    )                                                                    AS attendance_pct
FROM edu.user       u
JOIN edu.attendance a ON a.user_id    = u.user_id
JOIN edu.subject    s ON s.subject_id = a.subject_id
GROUP BY u.user_id, u.user_nickname, u.first_name, u.surname,
         s.subject_id, s.subject_name, s.semestr, a.lesson_type;

-- ---------------------------------------------------------------------------
-- 3. exam_statistics_view
--    Количество зарегистрированных студентов и успешность сдачи по экзамену
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW edu.exam_statistics_view AS
SELECT
    e.exam_id,
    e.exam_date,
    e.exam_time,
    e.exam_type,
    e.passed_type,
    s.subject_id,
    s.subject_name,
    COUNT(ue.user_id)                                                    AS registered_count,
    COUNT(sc.score_id) FILTER (WHERE sc.is_passed = TRUE)               AS passed_count,
    COUNT(sc.score_id) FILTER (WHERE sc.is_passed = FALSE)              AS failed_count,
    ROUND(
        COUNT(sc.score_id) FILTER (WHERE sc.is_passed = TRUE)::NUMERIC /
        NULLIF(COUNT(ue.user_id), 0) * 100, 2
    )                                                                    AS pass_rate_pct
FROM edu.exam        e
JOIN edu.subject     s  ON s.subject_id = e.subject_id
LEFT JOIN edu.user_exam ue ON ue.exam_id   = e.exam_id
LEFT JOIN edu.score     sc ON sc.user_id   = ue.user_id
                           AND sc.subject_id = e.subject_id
GROUP BY e.exam_id, e.exam_date, e.exam_time, e.exam_type, e.passed_type,
         s.subject_id, s.subject_name;

-- ---------------------------------------------------------------------------
-- 4. user_activity_view
--    Количество сессий и событий по студенту
--    Требует: edu.session, edu.event (из ER-модели)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW edu.user_activity_view AS
SELECT
    u.user_id,
    u.user_nickname,
    u.first_name,
    u.surname,
    COUNT(DISTINCT ss.session_id)                                        AS session_count,
    COUNT(ev.event_id)                                                   AS event_count,
    COUNT(DISTINCT ev.page_id)                                           AS unique_pages,
    MAX(ss.session_start)                                                AS last_session
FROM edu.user     u
LEFT JOIN edu.session ss ON ss.user_id    = u.user_id
LEFT JOIN edu.event   ev ON ev.session_id = ss.session_id
GROUP BY u.user_id, u.user_nickname, u.first_name, u.surname;
