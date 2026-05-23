"""ClickHouse connection via clickhouse-connect."""

from __future__ import annotations

import streamlit as st
import clickhouse_connect
from clickhouse_connect.driver.client import Client

from app.config import get_settings
from app.utils.logger import get_logger

log = get_logger(__name__)


@st.cache_resource
def get_ch_client() -> Client:
    settings = get_settings()
    log.info("Creating ClickHouse client: %s", settings.clickhouse_host)
    client = clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
        database=settings.clickhouse_database,
        connect_timeout=10,
        query_retries=2,
    )
    client.ping()
    log.info("ClickHouse connected.")
    return client
