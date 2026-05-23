-- =============================================================================
-- PostgreSQL OLTP Schema — Electronic University
-- Source of truth: README.md ER model
-- Schema: edu
-- Содержит: USER, STUDY_GROUP, PROGRAM, EDUCATION_DEGREE, EDUCATION_FORM,
--           FACULTY, DEPARTMENT, SUBJECT, EXAM, SCORE, ATTENDANCE,
--           USER_STUDY_GROUP, USER_SUBJECT, USER_EXAM, PAGE
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS edu;

-- ---------------------------------------------------------------------------
-- EDUCATION_DEGREE
-- ---------------------------------------------------------------------------
CREATE TABLE edu.education_degree (
    degree_id   SERIAL       PRIMARY KEY,
    degree_name VARCHAR(100) NOT NULL
);

-- ---------------------------------------------------------------------------
-- EDUCATION_FORM
-- ---------------------------------------------------------------------------
CREATE TABLE edu.education_form (
    form_id   SERIAL       PRIMARY KEY,
    form_name VARCHAR(100) NOT NULL
);

-- ---------------------------------------------------------------------------
-- FACULTY
-- ---------------------------------------------------------------------------
CREATE TABLE edu.faculty (
    faculty_id   SERIAL       PRIMARY KEY,
    faculty_name VARCHAR(100) NOT NULL
);

-- ---------------------------------------------------------------------------
-- DEPARTMENT
-- ---------------------------------------------------------------------------
CREATE TABLE edu.department (
    department_id   SERIAL       PRIMARY KEY,
    faculty_id      INT          NOT NULL REFERENCES edu.faculty(faculty_id),
    department_name VARCHAR(100) NOT NULL
);

-- ---------------------------------------------------------------------------
-- PROGRAM
-- ---------------------------------------------------------------------------
CREATE TABLE edu.program (
    program_id     SERIAL       PRIMARY KEY,
    degree_id      INT          NOT NULL REFERENCES edu.education_degree(degree_id),
    form_id        INT          NOT NULL REFERENCES edu.education_form(form_id),
    department_id  INT          NOT NULL REFERENCES edu.department(department_id),
    education_code VARCHAR(50)  NOT NULL,
    year_of_study  INT          NOT NULL,
    profile        VARCHAR(100),
    speciality     VARCHAR(100) NOT NULL
);

-- ---------------------------------------------------------------------------
-- STUDY_GROUP
-- AK 1.1+1.2: (group_name, enrollment_year)
-- ---------------------------------------------------------------------------
CREATE TABLE edu.study_group (
    group_id        SERIAL      PRIMARY KEY,
    program_id      INT         NOT NULL REFERENCES edu.program(program_id),
    group_name      VARCHAR(50) NOT NULL,
    enrollment_year INT         NOT NULL,
    course          INT,
    semestr         INT         NOT NULL,
    UNIQUE (group_name, enrollment_year)
);

-- ---------------------------------------------------------------------------
-- USER
-- AK 1.1: user_nickname
-- ---------------------------------------------------------------------------
CREATE TABLE edu.user (
    user_id            SERIAL       PRIMARY KEY,
    user_nickname      VARCHAR(10)   NOT NULL UNIQUE,
    first_name         VARCHAR(100) NOT NULL,
    surname            VARCHAR(100) NOT NULL,
    middle_name        VARCHAR(100),
    birth_date         DATE         NOT NULL,
    gender             VARCHAR(10)  NOT NULL,
    citizenship        VARCHAR(100) NOT NULL,
    enrollment_year    INT          NOT NULL,
    funding_type       VARCHAR(50)  NOT NULL,
    dormitory_resident BOOLEAN      NOT NULL,
    status             VARCHAR(50)  NOT NULL,
    current_course     INT          NOT NULL
);

-- ---------------------------------------------------------------------------
-- USER_STUDY_GROUP  (M:N)
-- ---------------------------------------------------------------------------
CREATE TABLE edu.user_study_group (
    user_id  INT NOT NULL REFERENCES edu.user(user_id),
    group_id INT NOT NULL REFERENCES edu.study_group(group_id),
    PRIMARY KEY (user_id, group_id)
);

-- ---------------------------------------------------------------------------
-- SUBJECT
-- ---------------------------------------------------------------------------
CREATE TABLE edu.subject (
    subject_id   SERIAL       PRIMARY KEY,
    subject_name VARCHAR(200) NOT NULL,
    semestr      INT          NOT NULL,
    credit_hours INT          NOT NULL,
    department   VARCHAR(100) NOT NULL,
    type         VARCHAR(50)  NOT NULL,
    count_labs   INT,
    count_rk     INT,
    count_dz     INT
);

-- ---------------------------------------------------------------------------
-- USER_SUBJECT  (M:N)
-- ---------------------------------------------------------------------------
CREATE TABLE edu.user_subject (
    user_id    INT NOT NULL REFERENCES edu.user(user_id),
    subject_id INT NOT NULL REFERENCES edu.subject(subject_id),
    PRIMARY KEY (user_id, subject_id)
);

-- ---------------------------------------------------------------------------
-- EXAM
-- AK 1.1+1.2+1.3: (subject_id, exam_date, exam_time)
-- ---------------------------------------------------------------------------
CREATE TABLE edu.exam (
    exam_id     SERIAL      PRIMARY KEY,
    subject_id  INT         NOT NULL REFERENCES edu.subject(subject_id),
    exam_date   DATE        NOT NULL,
    exam_time   TIME        NOT NULL,
    exam_type   VARCHAR(50) NOT NULL,
    passed_type VARCHAR(50) NOT NULL,
    UNIQUE (subject_id, exam_date, exam_time)
);

-- ---------------------------------------------------------------------------
-- USER_EXAM  (M:N)
-- ---------------------------------------------------------------------------
CREATE TABLE edu.user_exam (
    user_id INT NOT NULL REFERENCES edu.user(user_id),
    exam_id INT NOT NULL REFERENCES edu.exam(exam_id),
    PRIMARY KEY (user_id, exam_id)
);

-- ---------------------------------------------------------------------------
-- PAGE  (справочник страниц)
-- AK 1.1: page_path
-- ---------------------------------------------------------------------------
CREATE TABLE edu.page (
    page_id      SERIAL       PRIMARY KEY,
    page_path    VARCHAR(255) NOT NULL UNIQUE,
    page_name    VARCHAR(255) NOT NULL,
    page_section VARCHAR(100) NOT NULL
);

-- ---------------------------------------------------------------------------
-- ATTENDANCE
-- ---------------------------------------------------------------------------
CREATE TABLE edu.attendance (
    attendance_id SERIAL      PRIMARY KEY,
    subject_id    INT         NOT NULL REFERENCES edu.subject(subject_id),
    user_id       INT         NOT NULL REFERENCES edu.user(user_id),
    lesson_date   DATE        NOT NULL,
    lesson_time   TIME        NOT NULL,
    lesson_type   VARCHAR(50) NOT NULL,
    is_present    BOOLEAN     NOT NULL
);

-- ---------------------------------------------------------------------------
-- SCORE
-- ---------------------------------------------------------------------------
CREATE TABLE edu.score (
    score_id       SERIAL      PRIMARY KEY,
    subject_id     INT         NOT NULL REFERENCES edu.subject(subject_id),
    user_id        INT         NOT NULL REFERENCES edu.user(user_id),
    score_date     DATE        NOT NULL,
    score_type     VARCHAR(50) NOT NULL,
    score          INT         NOT NULL,
    max_score      INT         NOT NULL,
    attempt_number INT         NOT NULL,
    is_passed      BOOLEAN     NOT NULL,
    module         INT         NOT NULL
);
