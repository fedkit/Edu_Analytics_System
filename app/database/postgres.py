"""PostgreSQL connection via SQLAlchemy."""

from __future__ import annotations

import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.config import get_settings
from app.utils.logger import get_logger

log = get_logger(__name__)


@st.cache_resource
def get_pg_engine() -> Engine:
    settings = get_settings()
    log.info("Creating PostgreSQL engine: %s", settings.postgres_db)
    engine = create_engine(
        settings.postgres_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
    # Verify connectivity
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    log.info("PostgreSQL connected.")
    return engine
