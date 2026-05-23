-- =============================================================================
-- PostgreSQL Functions — Electronic University
-- Только бизнес-логика: GPA, посещаемость, прогресс, экзамены
-- =============================================================================

SET search_path = edu;

-- ===========================================================================
-- 1. calculate_gpa(user_id)
--    Средневзвешенный балл студента по всем оценкам в процентах.
--    Учитывает все попытки.
-- ===========================================================================
CREATE OR REPLACE FUNCTION edu.calculate_gpa(p_user_id INT)
RETURNS NUMERIC
LANGUAGE sql STABLE
AS $$
    SELECT ROUND(
        SUM(score)::NUMERIC / NULLIF(SUM(max_score), 0) * 100,
        2
    )
    FROM edu.score
    WHERE user_id = p_user_id;
$$;

-- ===========================================================================
-- 2. calculate_attendance_rate(user_id)
--    Общий процент посещаемости студента по всем предметам.
-- ===========================================================================
CREATE OR REPLACE FUNCTION edu.calculate_attendance_rate(p_user_id INT)
RETURNS NUMERIC
LANGUAGE sql STABLE
AS $$
    SELECT ROUND(
        SUM(is_present::INT)::NUMERIC /
        NULLIF(COUNT(*), 0) * 100,
        2
    )
    FROM edu.attendance
    WHERE user_id = p_user_id;
$$;

-- ===========================================================================
-- 3. get_user_progress(user_id)
--    Сводка по предметам: баллы + посещаемость в одной таблице.
-- ===========================================================================
CREATE OR REPLACE FUNCTION edu.get_user_progress(p_user_id INT)
RETURNS TABLE (
    subject_id       INT,
    subject_name     VARCHAR(200),
    semestr          INT,
    avg_score_pct    NUMERIC,
    passed_scores    BIGINT,
    total_scores     BIGINT,
    attendance_pct   NUMERIC,
    attended_lessons BIGINT,
    total_lessons    BIGINT
)
LANGUAGE sql STABLE
AS $$
    SELECT
        s.subject_id,
        s.subject_name,
        s.semestr,
        ROUND(
            SUM(sc.score)::NUMERIC / NULLIF(SUM(sc.max_score), 0) * 100,
            2
        )                                                   AS avg_score_pct,
        COUNT(sc.score_id) FILTER (WHERE sc.is_passed)     AS passed_scores,
        COUNT(sc.score_id)                                  AS total_scores,
        ROUND(
            SUM(a.is_present::INT)::NUMERIC /
            NULLIF(COUNT(a.attendance_id), 0) * 100,
            2
        )                                                   AS attendance_pct,
        SUM(a.is_present::INT)                              AS attended_lessons,
        COUNT(a.attendance_id)                              AS total_lessons
    FROM edu.user_subject us
    JOIN edu.subject    s  ON s.subject_id  = us.subject_id
    LEFT JOIN edu.score sc ON sc.user_id    = p_user_id
                           AND sc.subject_id = s.subject_id
    LEFT JOIN edu.attendance a ON a.user_id    = p_user_id
                               AND a.subject_id = s.subject_id
    WHERE us.user_id = p_user_id
    GROUP BY s.subject_id, s.subject_name, s.semestr
    ORDER BY s.semestr, s.subject_name;
$$;

-- ===========================================================================
-- 4. get_exam_results(user_id)
--    Список экзаменов студента с результатами из score.
--    Связь: user_exam → exam → subject, score по (user_id, subject_id).
-- ===========================================================================
CREATE OR REPLACE FUNCTION edu.get_exam_results(p_user_id INT)
RETURNS TABLE (
    exam_id      INT,
    subject_name VARCHAR(200),
    exam_date    DATE,
    exam_time    TIME,
    exam_type    VARCHAR(50),
    passed_type  VARCHAR(50),
    score        INT,
    max_score    INT,
    score_pct    NUMERIC,
    is_passed    BOOLEAN,
    attempt_number INT
)
LANGUAGE sql STABLE
AS $$
    SELECT
        e.exam_id,
        s.subject_name,
        e.exam_date,
        e.exam_time,
        e.exam_type,
        e.passed_type,
        sc.score,
        sc.max_score,
        ROUND(sc.score::NUMERIC / NULLIF(sc.max_score, 0) * 100, 2) AS score_pct,
        sc.is_passed,
        sc.attempt_number
    FROM edu.user_exam  ue
    JOIN edu.exam        e  ON e.exam_id    = ue.exam_id
    JOIN edu.subject     s  ON s.subject_id = e.subject_id
    LEFT JOIN edu.score  sc ON sc.user_id   = ue.user_id
                            AND sc.subject_id = e.subject_id
    WHERE ue.user_id = p_user_id
    ORDER BY e.exam_date, e.exam_time;
$$;
