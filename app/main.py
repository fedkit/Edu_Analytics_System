"""
Electronic University Analytics Platform
Streamlit entry point.

Run:
    streamlit run app/main.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from app.config import get_settings
from app.database.clickhouse import get_ch_client
from app.database.postgres import get_pg_engine
from app.repositories.academic_repo import AcademicRepository
from app.repositories.behavior_repo import BehaviorRepository
from app.components.filters import render_sidebar

# ── Page config ───────────────────────────────────────────────────────────────
settings = get_settings()
st.set_page_config(
    page_title=settings.app_title,
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .block-container { padding-top: 1rem; }
    [data-testid="metric-container"] {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 8px;
        padding: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Navigation ────────────────────────────────────────────────────────────────
PAGES = {
    "📊 Дашборд":          "dashboard",
    "🔍 Поведение":        "behavior",
    "🎯 Воронки":          "funnel",
    "🔄 Retention":        "retention",
    "📌 Stickiness":       "stickiness",
    "🎲 RFM-анализ":       "rfm",
    "🎓 Академика":        "academic",
    "🔗 Корреляции":       "correlation",
    "👤 Профиль студента": "student_profile",
    "⚠️ Риски":            "alerts",
}

with st.sidebar:
    st.title("🎓 EduAnalytics")
    st.caption(settings.app_title)
    st.divider()
    page_name = st.radio(
        "Страница", list(PAGES.keys()), label_visibility="collapsed"
    )
    st.divider()

page_key = PAGES[page_name]

# ── DB connections ────────────────────────────────────────────────────────────
try:
    engine = get_pg_engine()
    ch     = get_ch_client()
except Exception as e:
    st.error(f"Ошибка подключения к базе данных: {e}")
    st.stop()

academic = AcademicRepository(engine)
behavior = BehaviorRepository(ch)

# ── Load dimension data for filters ──────────────────────────────────────────
try:
    fac_df  = academic.get_faculties()
    grp_df  = academic.get_study_groups()
    subj_df = academic.get_subjects()
    faculties = list(zip(fac_df["faculty_id"], fac_df["faculty_name"]))
    groups    = list(zip(grp_df["group_id"],   grp_df["group_name"]))
    subjects  = list(zip(subj_df["subject_id"], subj_df["subject_name"]))
except Exception:
    faculties, groups, subjects = [], [], []

# ── Sidebar filters ───────────────────────────────────────────────────────────
f = render_sidebar(faculties=faculties, groups=groups, subjects=subjects)

# ── Render selected page ──────────────────────────────────────────────────────
try:
    match page_key:
        case "dashboard":
            from app.pages.dashboard import render
            render(f, academic, behavior)

        case "behavior":
            from app.pages.behavior import render
            render(f, behavior)

        case "funnel":
            from app.pages.funnel import render
            render(f, behavior)

        case "retention":
            from app.pages.retention import render
            render(f, behavior)

        case "stickiness":
            from app.pages.stickiness import render
            render(f, behavior)

        case "rfm":
            from app.pages.rfm import render
            render(f, behavior, academic)

        case "academic":
            from app.pages.academic import render
            render(f, academic)

        case "correlation":
            from app.pages.correlation import render
            render(f, behavior, academic)

        case "student_profile":
            from app.pages.student_profile import render
            render(f, academic, behavior)

        case "alerts":
            from app.pages.alerts import render
            render(f, academic, behavior)

except Exception as e:
    import traceback
    st.error(f"Ошибка при загрузке страницы: {e}")
    with st.expander("Traceback"):
        st.code(traceback.format_exc())
