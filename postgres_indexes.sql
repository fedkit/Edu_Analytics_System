-- =============================================================================
-- PostgreSQL Indexes — Electronic University
-- Основаны строго на таблицах из clean_postgres_schema.sql
-- + session / event (из ER-модели)
-- =============================================================================

SET search_path = edu;

-- ---------------------------------------------------------------------------
-- FK indexes
-- ---------------------------------------------------------------------------

-- department → faculty
CREATE INDEX idx_department_faculty_id    ON edu.department(faculty_id);

-- program → degree / form / department
CREATE INDEX idx_program_degree_id        ON edu.program(degree_id);
CREATE INDEX idx_program_form_id          ON edu.program(form_id);
CREATE INDEX idx_program_department_id    ON edu.program(department_id);

-- study_group → program
CREATE INDEX idx_study_group_program_id   ON edu.study_group(program_id);

-- user_study_group: user_id covered by PK(user_id, group_id); need reverse direction
CREATE INDEX idx_user_study_group_group   ON edu.user_study_group(group_id);

-- user_subject: subject direction
CREATE INDEX idx_user_subject_subject_id  ON edu.user_subject(subject_id);

-- user_exam: exam direction
CREATE INDEX idx_user_exam_exam_id        ON edu.user_exam(exam_id);

-- exam → subject
CREATE INDEX idx_exam_subject_id          ON edu.exam(subject_id);

-- attendance → subject, user
CREATE INDEX idx_attendance_subject_id    ON edu.attendance(subject_id);
CREATE INDEX idx_attendance_user_id       ON edu.attendance(user_id);

-- score → subject, user
CREATE INDEX idx_score_subject_id         ON edu.score(subject_id);
CREATE INDEX idx_score_user_id            ON edu.score(user_id);

-- session / event живут в ClickHouse — индексы там не нужны

-- ---------------------------------------------------------------------------
-- Date / time filter indexes
-- ---------------------------------------------------------------------------

CREATE INDEX idx_score_date               ON edu.score(score_date);
CREATE INDEX idx_attendance_lesson_date   ON edu.attendance(lesson_date);
CREATE INDEX idx_exam_date                ON edu.exam(exam_date);
-- event_time / session_start — индексы в ClickHouse

-- ---------------------------------------------------------------------------
-- Composite indexes for analytical queries
-- ---------------------------------------------------------------------------

-- score per student per subject (GPA, progress queries)
CREATE INDEX idx_score_user_subject       ON edu.score(user_id, subject_id);

-- attendance per student per subject
CREATE INDEX idx_attendance_user_subject  ON edu.attendance(user_id, subject_id);

-- session/event composite indexes — в ClickHouse
