-- =============================================================================
-- ClickHouse OLAP Schema — Electronic University
-- Содержит ТОЛЬКО: SESSION, EVENT, PAGE (dimension copy)
-- Поведенческая аналитика пользователей
-- =============================================================================

CREATE DATABASE IF NOT EXISTS edu_analytics;

-- ---------------------------------------------------------------------------
-- PAGE — dimension copy из PostgreSQL (синхронизируется через ETL)
-- ReplacingMergeTree: дедупликация по page_id при повторной загрузке
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS edu_analytics.page
(
    page_id      UInt32,
    page_path    String,
    page_name    String,
    page_section String
)
ENGINE = ReplacingMergeTree()
ORDER BY page_id;

-- ---------------------------------------------------------------------------
-- SESSION — факты пользовательских сессий
-- Partition by: месяц начала сессии
-- Order by: user_id, session_id (основные фильтры — по пользователю)
-- ReplacingMergeTree: ETL может перезаписывать строку при закрытии сессии
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS edu_analytics.session
(
    session_id    UInt32,
    user_id       UInt32,
    session_start DateTime,
    session_end   Nullable(DateTime),
    device_type   LowCardinality(String)
)
ENGINE = ReplacingMergeTree()
PARTITION BY toYYYYMM(session_start)
ORDER BY (user_id, session_id);

-- ---------------------------------------------------------------------------
-- EVENT — действия пользователя внутри сессии (append-only)
-- Partition by: месяц события
-- Order by: session_id, event_time — оптимально для timeline-запросов
-- MergeTree: события неизменяемы, вставка только append
-- AK 1.1+1.2: (session_id, event_time) — уникальность гарантируется
--             на уровне источника данных (PostgreSQL или application)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS edu_analytics.event
(
    event_id     UInt64,
    page_id      UInt32,
    next_page_id Nullable(UInt32),
    session_id   UInt32,
    event_time   DateTime,
    event_type   LowCardinality(String),
    element_name Nullable(String),
    purpose      Nullable(String)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(event_time)
ORDER BY (session_id, event_time);
