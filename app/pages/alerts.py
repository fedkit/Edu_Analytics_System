"""Alerts / Early Warning System page."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from app.components.charts import PLOTLY_CONFIG, bar_chart, line_chart
from app.components.filters import FilterState
from app.repositories.academic_repo import AcademicRepository
from app.repositories.behavior_repo import BehaviorRepository


def render(
    f: FilterState,
    academic: AcademicRepository,
    behavior: BehaviorRepository,
) -> None:
    st.title("⚠️ Система раннего предупреждения")
    st.caption(f"Анализ: {f.start_date} — {f.end_date}")

    with st.spinner("Анализ групп риска…"):
        at_risk   = academic.get_at_risk_students()
        beh_df    = behavior.get_per_user_behavior(f.start_date, f.end_date)
        acad_df   = academic.get_per_user_academic_summary(f.start_date, f.end_date)

    # ── Summary cards ─────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Всего в группе риска", len(at_risk), delta=None)

    low_score = at_risk[at_risk["avg_score_pct"] < 50]
    col2.metric("Критически низкий балл (<50%)", len(low_score))

    low_att = at_risk[at_risk["att_pct"] < 40]
    col3.metric("Критическая посещ. (<40%)", len(low_att))

    inactive = _find_inactive_users(beh_df, days=14, ref_date=f.end_date)
    col4.metric(f"Нет входа >14 дней", len(inactive))

    st.divider()

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tabs = st.tabs([
        "Группа риска", "Низкая активность", "Падение GPA", "Чёрный список"
    ])

    # ─── Tab 1: At-risk ───────────────────────────────────────────────────────
    with tabs[0]:
        st.subheader("Студенты в группе риска (балл < 60% или посещ. < 50%)")
        if at_risk.empty:
            st.success("Нет студентов в группе риска.")
        else:
            # Filters
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                score_thresh = st.slider("Порог среднего балла (%)", 0, 100, 60, key="ar_score")
            with col_f2:
                att_thresh = st.slider("Порог посещаемости (%)", 0, 100, 50, key="ar_att")

            filtered = at_risk[
                (at_risk["avg_score_pct"] < score_thresh) |
                (at_risk["att_pct"] < att_thresh)
            ]
            st.caption(f"Показано: {len(filtered)} студентов")

            fig = bar_chart(
                filtered["faculty_name"].value_counts().reset_index(),
                x="faculty_name", y="count",
                title="Распределение по факультетам",
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

            st.dataframe(
                filtered[[
                    "user_id", "user_nickname", "first_name", "surname",
                    "status", "current_course", "group_name",
                    "avg_score_pct", "att_pct", "faculty_name",
                ]].rename(columns={
                    "user_id": "ID", "user_nickname": "Никнейм",
                    "first_name": "Имя", "surname": "Фамилия",
                    "status": "Статус", "current_course": "Курс",
                    "group_name": "Группа", "avg_score_pct": "Ср. балл (%)",
                    "att_pct": "Посещ. (%)", "faculty_name": "Факультет",
                }),
                use_container_width=True, hide_index=True,
            )

    # ─── Tab 2: Inactive ──────────────────────────────────────────────────────
    with tabs[1]:
        st.subheader("Студенты без входа в систему")
        days_thresh = st.slider("Дней без активности", 3, 60, 14, key="inactive_days")
        inactive_list = _find_inactive_users(beh_df, days=days_thresh, ref_date=f.end_date)

        st.metric(f"Нет входа > {days_thresh} дней", len(inactive_list))

        if not inactive_list.empty:
            # Merge with academic for context
            merged_inactive = inactive_list.merge(
                acad_df[["user_id", "avg_score_pct"]], on="user_id", how="left"
            )
            fig = bar_chart(
                merged_inactive["avg_score_pct"].fillna(0)
                .apply(lambda x: "0-40%" if x < 40 else ("40-60%" if x < 60 else "60-80%" if x < 80 else "80-100%"))
                .value_counts()
                .reset_index(),
                x="avg_score_pct", y="count",
                title="Неактивные студенты: распределение по успеваемости",
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

            st.dataframe(
                merged_inactive[["user_id", "last_active", "session_count",
                                  "event_count", "avg_score_pct"]].rename(columns={
                    "user_id": "ID", "last_active": "Последний вход",
                    "session_count": "Сессий", "event_count": "События",
                    "avg_score_pct": "Ср. балл (%)",
                }),
                use_container_width=True, hide_index=True,
            )

    # ─── Tab 3: GPA drop ──────────────────────────────────────────────────────
    with tabs[2]:
        st.subheader("Падение GPA: тренд")
        gpa_ts = academic.get_gpa_timeseries(f.start_date, f.end_date)
        if not gpa_ts.empty:
            # Detect falling streak
            gpa_ts["delta"] = gpa_ts["avg_score_pct"].diff()
            falls = gpa_ts[gpa_ts["delta"] < -2]
            st.metric("Дней с падением балла >2%", len(falls))

            from app.analytics.anomaly import add_anomaly_column
            gpa_ts = add_anomaly_column(gpa_ts, "avg_score_pct")
            from app.services.trend_service import add_moving_average
            gpa_ts = add_moving_average(gpa_ts, "avg_score_pct", 7)

            fig = line_chart(
                gpa_ts, "score_date", "avg_score_pct",
                title="Средний балл с аномалиями",
                y_label="Балл (%)", ma_col="avg_score_pct_ma7",
                anomaly_col="is_anomaly",
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    # ─── Tab 4: Churn risk ────────────────────────────────────────────────────
    with tabs[3]:
        st.subheader("Высокий риск отчисления")
        if at_risk.empty or beh_df.empty:
            st.info("Нет данных.")
        else:
            churn = at_risk.merge(
                beh_df[["user_id", "session_count", "last_active"]],
                on="user_id", how="left",
            )
            churn["last_active"] = pd.to_datetime(churn["last_active"])
            churn["days_inactive"] = (
                pd.Timestamp(f.end_date) - churn["last_active"]
            ).dt.days.fillna(999)

            # High risk: low score + low attendance + long inactive
            churn["risk_score"] = (
                (100 - churn["avg_score_pct"].fillna(50)) * 0.4 +
                (100 - churn["att_pct"].fillna(50)) * 0.4 +
                churn["days_inactive"].clip(0, 30) * 0.7
            ).round(1)

            churn_high = churn.nlargest(50, "risk_score")
            st.caption("Топ-50 студентов с наибольшим риском отчисления")
            st.dataframe(
                churn_high[[
                    "user_id", "user_nickname", "group_name", "faculty_name",
                    "avg_score_pct", "att_pct", "days_inactive", "risk_score",
                ]].rename(columns={
                    "user_id": "ID", "user_nickname": "Никнейм",
                    "group_name": "Группа", "faculty_name": "Факультет",
                    "avg_score_pct": "Балл (%)", "att_pct": "Посещ. (%)",
                    "days_inactive": "Дней без входа", "risk_score": "Риск-балл",
                }),
                use_container_width=True, hide_index=True,
            )


def _find_inactive_users(beh_df: pd.DataFrame, days: int, ref_date: date) -> pd.DataFrame:
    if beh_df.empty:
        return pd.DataFrame()
    df = beh_df.copy()
    df["last_active"] = pd.to_datetime(df["last_active"])
    cutoff = pd.Timestamp(ref_date) - pd.Timedelta(days=days)
    return df[df["last_active"] < cutoff][["user_id", "last_active", "session_count", "event_count"]]
