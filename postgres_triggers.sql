-- =============================================================================
-- PostgreSQL Triggers — Electronic University
-- Только data integrity триггеры, без audit и event sourcing
-- =============================================================================

SET search_path = edu;

-- ---------------------------------------------------------------------------
-- Примечание: в таблицах отсутствует поле updated_at (не задано в ER-модели),
-- поэтому updated_at триггеры не добавляются.
-- ---------------------------------------------------------------------------

-- ===========================================================================
-- VALIDATION: session_end >= session_start
-- ===========================================================================
CREATE OR REPLACE FUNCTION edu.trg_validate_session()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.session_end IS NOT NULL AND NEW.session_end < NEW.session_start THEN
        RAISE EXCEPTION
            'session_end (%) must be >= session_start (%)',
            NEW.session_end, NEW.session_start;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_session_check_dates
    BEFORE INSERT OR UPDATE ON edu.session
    FOR EACH ROW EXECUTE FUNCTION edu.trg_validate_session();

-- ===========================================================================
-- VALIDATION: score <= max_score  AND  attempt_number >= 1
-- ===========================================================================
CREATE OR REPLACE FUNCTION edu.trg_validate_score()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.score > NEW.max_score THEN
        RAISE EXCEPTION
            'score (%) cannot exceed max_score (%) — score_id=%',
            NEW.score, NEW.max_score, NEW.score_id;
    END IF;

    IF NEW.attempt_number < 1 THEN
        RAISE EXCEPTION
            'attempt_number must be >= 1, got % — score_id=%',
            NEW.attempt_number, NEW.score_id;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_score_validate
    BEFORE INSERT OR UPDATE ON edu.score
    FOR EACH ROW EXECUTE FUNCTION edu.trg_validate_score();

-- ===========================================================================
-- VALIDATION: event_time within session bounds
-- Событие не может произойти раньше начала сессии или после её завершения
-- ===========================================================================
CREATE OR REPLACE FUNCTION edu.trg_validate_event_time()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_session_start TIMESTAMPTZ;
    v_session_end   TIMESTAMPTZ;
BEGIN
    SELECT session_start, session_end
      INTO v_session_start, v_session_end
      FROM edu.session
     WHERE session_id = NEW.session_id;

    IF NEW.event_time < v_session_start THEN
        RAISE EXCEPTION
            'event_time (%) is before session_start (%) for session_id=%',
            NEW.event_time, v_session_start, NEW.session_id;
    END IF;

    IF v_session_end IS NOT NULL AND NEW.event_time > v_session_end THEN
        RAISE EXCEPTION
            'event_time (%) is after session_end (%) for session_id=%',
            NEW.event_time, v_session_end, NEW.session_id;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_event_validate_time
    BEFORE INSERT ON edu.event
    FOR EACH ROW EXECUTE FUNCTION edu.trg_validate_event_time();
