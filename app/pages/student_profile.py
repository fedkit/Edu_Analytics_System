"""Student Profile page — full individual timeline."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components.charts import PLOTLY_CONFIG, bar_chart, line_chart, pie_chart
from app.components.filters import FilterState
from app.repositories.academic_repo import AcademicRepository
from app.repositories.behavior_repo import BehaviorRepository
from app.services.trend_service import add_moving_average


def render(
    f: FilterState,
    academic: AcademicRepository,
    behavior: BehaviorRepository,
) -> None:
    st.title("👤 Профиль студента")

    # ── Search ────────────────────────────────────────────────────────────────
    col_s1, col_s2 = st.columns([1, 2])
    with col_s1:
        search_type = st.radio("Поиск по", ["user_id", "nickname"], horizontal=True)
    with col_s2:
        query = st.text_input(
            "ID или никнейм" if search_type == "user_id" else "Никнейм",
            key="student_search",
        )

    if not query:
        st.info("Введите ID студента или никнейм для поиска.")
        return

    # Resolve user_id
    if search_type == "user_id":
        try:
            uid = int(query)
        except ValueError:
            st.error("Введите числовой user_id.")
            return
    else:
        all_users = academic.get_users()
        match = all_users[all_users["user_nickname"].str.lower() == query.lower()]
        if match.empty:
            st.error(f"Студент с никнеймом '{query}' не найден.")
            return
        uid = int(match.iloc[0]["user_id"])

    # ── Load profile ──────────────────────────────────────────────────────────
    with st.spinner("Загрузка профиля…"):
        profile_df = academic.get_user_by_id(uid)
        scores_df  = academic.get_scores_for_user(uid)
        att_df     = academic.get_attendance_for_user(uid)
        exams_df   = academic.get_exams_for_user(uid)
        sessions_df = behavior.get_sessions_for_user(uid)

    if profile_df.empty:
        st.error(f"Студент с ID {uid} не найден.")
        return

    p = profile_df.iloc[0]

    # ── Header card ───────────────────────────────────────────────────────────
    st.subheader(f"{p.get('surname', '')} {p.get('first_name', '')} {p.get('middle_name', '') or ''}")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Никнейм",   p.get("user_nickname", "—"))
    col2.metric("Статус",    p.get("status", "—"))
    col3.metric("Курс",      p.get("current_course", "—"))
    col4.metric("Группа",    p.get("group_name", "—"))

    col5, col6, col7 = st.columns(3)
    col5.metric("Факультет",   p.get("faculty_name", "—"))
    col6.metric("Год поступ.", p.get("enrollment_year", "—"))
    col7.metric("Финансирование", p.get("funding_type", "—"))

    st.divider()

    # ── KPIs ──────────────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5 = st.columns(5)
    if not scores_df.empty:
        avg_score = scores_df["score_pct"].mean()
        pass_rate = scores_df["is_passed"].mean() * 100
        k1.metric("Ср. балл (%)",  f"{avg_score:.1f}%")
        k2.metric("Pass Rate",     f"{pass_rate:.1f}%")
    if not att_df.empty:
        att_pct = att_df["is_present"].mean() * 100
        k3.metric("Посещаемость",  f"{att_pct:.1f}%")
    if not sessions_df.empty:
        k4.metric("Сессий всего",  f"{len(sessions_df):,}")
        k5.metric("Последний вход", str(sessions_df["session_date"].max()))

    st.divider()

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tabs = st.tabs(["Академика", "Активность", "Совместный анализ"])

    # ─── Academic tab ─────────────────────────────────────────────────────────
    with tabs[0]:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("История оценок")
            if not scores_df.empty:
                scores_df["score_date"] = pd.to_datetime(scores_df["score_date"])
                fig = line_chart(
                    scores_df.sort_values("score_date"),
                    "score_date", "score_pct",
                    title="Балл (%) по времени",
                    y_label="Балл (%)",
                )
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

                fig = bar_chart(
                    scores_df.groupby("subject_name")["score_pct"].mean().reset_index()
                    .sort_values("score_pct"),
                    x="score_pct", y="subject_name",
                    title="Средний балл по предметам",
                    horizontal=True,
                )
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

                with st.expander("Все оценки"):
                    st.dataframe(
                        scores_df[["score_date","subject_name","score_type","score","max_score","score_pct","is_passed","module"]]
                        .rename(columns={
                            "score_date":"Дата","subject_name":"Предмет",
                            "score_type":"Тип","score":"Балл","max_score":"Макс.",
                            "score_pct":"% от макс.","is_passed":"Сдано","module":"Модуль",
                        }),
                        use_container_width=True, hide_index=True,
                    )
            else:
                st.info("Нет оценок.")

        with c2:
            st.subheader("Посещаемость")
            if not att_df.empty:
                att_df["lesson_date"] = pd.to_datetime(att_df["lesson_date"])
                daily_att = att_df.groupby("lesson_date")["is_present"].mean().reset_index()
                daily_att["is_present"] = (daily_att["is_present"] * 100).round(1)
                fig = line_chart(daily_att, "lesson_date", "is_present",
                                 title="Посещаемость по дням (%)", y_label="%")
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

                sub_att = att_df.groupby("subject_name")["is_present"].mean().reset_index()
                sub_att["is_present"] = (sub_att["is_present"] * 100).round(1)
                fig = bar_chart(
                    sub_att.sort_values("is_present"),
                    x="is_present", y="subject_name",
                    title="Посещаемость по предметам (%)",
                    horizontal=True,
                )
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
            else:
                st.info("Нет данных посещаемости.")

        st.subheader("Экзамены")
        if not exams_df.empty:
            st.dataframe(
                exams_df[["exam_date","subject_name","exam_type","passed_type"]]
                .rename(columns={"exam_date":"Дата","subject_name":"Предмет",
                                 "exam_type":"Тип","passed_type":"Форма"}),
                use_container_width=True, hide_index=True,
            )
        else:
            st.info("Нет данных по экзаменам.")

    # ─── Behavior tab ─────────────────────────────────────────────────────────
    with tabs[1]:
        st.subheader("История сессий")
        if not sessions_df.empty:
            sessions_df["session_date"] = pd.to_datetime(sessions_df["session_date"])
            daily_sess = sessions_df.groupby("session_date").agg(
                sessions=("session_id", "count"),
                events=("event_count", "sum"),
                avg_dur=("duration_min", "mean"),
            ).reset_index()

            fig = line_chart(
                daily_sess, "session_date", ["sessions", "events"],
                title="Сессии и события по дням",
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

            fig = line_chart(
                daily_sess, "session_date", "avg_dur",
                title="Средняя длительность сессии (мин)",
                y_label="Минуты",
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

            dev_dist = sessions_df["device_type"].value_counts().reset_index()
            dev_dist.columns = ["device_type", "count"]
            fig = pie_chart(dev_dist, "device_type", "count",
                            title="Устройства пользователя")
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

            with st.expander("Последние 20 сессий"):
                st.dataframe(
                    sessions_df.head(20)[
                        ["session_date","duration_min","event_count","device_type"]
                    ].rename(columns={
                        "session_date":"Дата","duration_min":"Длит.(мин)",
                        "event_count":"События","device_type":"Устройство",
                    }),
                    use_container_width=True, hide_index=True,
                )
        else:
            st.info("Нет данных о сессиях.")

    # ─── Combined tab ─────────────────────────────────────────────────────────
    with tabs[2]:
        st.subheader("Активность vs Оценки (совмещённый тренд)")
        if not sessions_df.empty and not scores_df.empty:
            daily_sess2 = sessions_df.groupby("session_date")["session_id"].count().reset_index()
            daily_sess2.columns = ["date", "sessions"]
            daily_scores2 = (
                scores_df.groupby("score_date")["score_pct"].mean().reset_index()
            )
            daily_scores2.columns = ["date", "score_pct"]

            daily_sess2["date"]   = pd.to_datetime(daily_sess2["date"])
            daily_scores2["date"] = pd.to_datetime(daily_scores2["date"])

            merged = daily_sess2.merge(daily_scores2, on="date", how="outer").sort_values("date")
            merged = merged.ffill()

            import plotly.graph_objects as go
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=merged["date"], y=merged["sessions"],
                                     name="Сессии", line=dict(color="#3498db")))
            fig.add_trace(go.Scatter(x=merged["date"], y=merged["score_pct"],
                                     name="Балл (%)", line=dict(color="#e74c3c"),
                                     yaxis="y2"))
            fig.update_layout(
                title="Сессии и балл (%) на одном графике",
                yaxis=dict(title="Сессии", side="left"),
                yaxis2=dict(title="Балл (%)", side="right", overlaying="y"),
                hovermode="x unified",
                legend=dict(orientation="h"),
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        else:
            st.info("Недостаточно данных для совмещённого анализа.")
