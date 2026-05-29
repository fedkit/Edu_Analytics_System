"""
EduAnalytics — Temporal Learning Analytics Platform
Запуск: streamlit run app/main.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

st.set_page_config(
    page_title="EduAnalytics",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container { padding-top: 0.8rem; padding-bottom: 1rem; }
    [data-testid="stSidebarNavItems"] li:first-child { display: none !important; }
    [data-testid="metric-container"] {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 10px;
        padding: 14px;
    }
    h2 { font-size: 1.25rem !important; margin-top: 1rem !important; }
    h3 { font-size: 1.05rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

_HERE = os.path.dirname(os.path.abspath(__file__))

pg = st.navigation({
    " ": [
        st.Page(
            "pages/academic.py",
            title="Академическая аналитика",
            default=True,
        ),
        st.Page(
            "pages/usage.py",
            title="Пользовательская аналитика",
        ),
        st.Page(
            "pages/correlation.py",
            title="Корреляция обучения",
        ),
    ],
})

pg.run()
