"""Streamlit-aware TTL cache helpers."""

from __future__ import annotations

import streamlit as st
from app.config import get_settings


def get_ttl() -> int:
    return get_settings().cache_ttl_seconds


def invalidate_all() -> None:
    """Clear all Streamlit caches (called by Refresh button)."""
    st.cache_data.clear()
    st.cache_resource.clear()
