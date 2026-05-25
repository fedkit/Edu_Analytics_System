"""Сервис академической аналитики: вычисление метрик из сырых данных."""
from __future__ import annotations

from datetime import date

import pandas as pd
from sqlalchemy.engine import Engine

from app.core.time_aggregation import add_rolling_avg, fill_date_gaps
from app.queries import postgres_queries as pg


def _safe_div(a: float, b: float, default: float | None = None) -> float | None:
    return round(a / b * 100, 1) if b and b > 0 else default


def status_label(pct: float | None) -> str:
    if pct is None or pd.isna(pct):
        return "Нет данных"
    if pct >= 80:
        return "Хорошо"
    if pct >= 60:
        return "Нормально"
    if pct >= 40:
        return "Риск"
    return "Критично"


def status_color(label: str) -> str:
    return {
        "Хорошо":    "#4CAF50",
        "Нормально": "#2196F3",
        "Риск":      "#FF9800",
        "Критично":  "#F44336",
    }.get(label, "#888")


# ─────────────────────────────────────────────────────────────────────────────

def load_academic_data(
    engine: Engine,
    start: date,
    end: date,
    student_id: int | None = None,
    group_id: int | None = None,
    faculty_id: int | None = None,
    subject_id: int | None = None,
    semester: int | None = None,
    course: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (scores_df, attendance_df) for the given scope."""
    scores = pg.load_scores_for_level(
        engine, start, end,
        student_id=student_id, group_id=group_id, faculty_id=faculty_id,
        subject_id=subject_id, semester=semester, course=course,
    )
    attendance = pg.load_attendance_for_level(
        engine, start, end,
        student_id=student_id, group_id=group_id, faculty_id=faculty_id,
        course=course,
    )
    return scores, attendance


def calculate_cumulative_scores(scores_df: pd.DataFrame, rolling: int = 7) -> pd.DataFrame:
    """
    Daily cumulative progress averaged per student.
    Returns: date, daily_score, daily_max, cum_score, cum_max, progress_pct, min_expected
    """
    if scores_df.empty:
        return pd.DataFrame()

    total_students = max(scores_df["user_id"].nunique(), 1)

    daily = (
        scores_df.groupby("date")
        .agg(daily_score=("score", "sum"), daily_max=("max_score", "sum"))
        .reset_index()
        .sort_values("date")
    )
    daily = fill_date_gaps(daily, "date", ["daily_score", "daily_max"])
    daily[["daily_score", "daily_max"]] = daily[["daily_score", "daily_max"]].fillna(0)

    daily["avg_score"] = (daily["daily_score"] / total_students).round(3)
    daily["avg_max"]   = (daily["daily_max"]   / total_students).round(3)

    daily["cum_score"] = daily["avg_score"].cumsum().round(2)
    daily["cum_max"]   = daily["avg_max"].cumsum().round(2)
    daily["progress_pct"] = (
        daily["cum_score"] / daily["cum_max"].replace(0, float("nan")) * 100
    ).round(1)
    daily["min_expected"] = (daily["cum_max"] * 0.6).round(2)

    daily = add_rolling_avg(daily, "date", "cum_score",    windows=[rolling])
    daily = add_rolling_avg(daily, "date", "progress_pct", windows=[rolling])
    return daily.reset_index(drop=True)


def calculate_weekly_velocity(scores_df: pd.DataFrame, rolling: int = 7) -> pd.DataFrame:
    """Weekly average score per student (bar chart data)."""
    if scores_df.empty:
        return pd.DataFrame()

    total_students = max(scores_df["user_id"].nunique(), 1)
    df = scores_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["week"] = df["date"].dt.to_period("W").dt.start_time

    weekly = (
        df.groupby("week")
        .agg(weekly_total=("score", "sum"))
        .reset_index()
    )
    weekly["avg_weekly_score"] = (weekly["weekly_total"] / total_students).round(2)
    weekly["is_zero"] = weekly["avg_weekly_score"] == 0
    return weekly.sort_values("week").reset_index(drop=True)


def calculate_risk_share(scores_df: pd.DataFrame) -> pd.DataFrame:
    """Weekly share (%) of students with cumulative progress < 60%."""
    if scores_df.empty or scores_df["user_id"].nunique() < 2:
        return pd.DataFrame()

    df = scores_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["user_id", "date"])

    df["cum_score"] = df.groupby("user_id")["score"].cumsum()
    df["cum_max"]   = df.groupby("user_id")["max_score"].cumsum()
    df["progress"]  = (df["cum_score"] / df["cum_max"].replace(0, float("nan")) * 100)
    df["is_risk"]   = (df["progress"] < 60) & df["progress"].notna()

    df["week"] = df["date"].dt.to_period("W").dt.start_time
    last = df.sort_values("date").groupby(["user_id", "week"]).last().reset_index()

    result = (
        last.groupby("week")
        .agg(risk_count=("is_risk", "sum"), total=("user_id", "nunique"))
        .reset_index()
    )
    result["risk_pct"] = (
        result["risk_count"] / result["total"].replace(0, float("nan")) * 100
    ).round(1)
    return result.sort_values("week").reset_index(drop=True)


def calculate_student_distribution(scores_df: pd.DataFrame) -> pd.DataFrame:
    """Per-student total progress distribution for histogram/boxplot."""
    if scores_df.empty:
        return pd.DataFrame()

    per = (
        scores_df.groupby("user_id")
        .agg(total_score=("score", "sum"), total_max=("max_score", "sum"))
        .reset_index()
    )
    per = per[per["total_max"] > 0].copy()
    per["progress_pct"] = (per["total_score"] / per["total_max"] * 100).round(1)
    return per


def calculate_attendance_vs_progress(
    scores_df: pd.DataFrame,
    attendance_df: pd.DataFrame,
    level: str,
    subject_names_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Scatter: attendance_rate vs progress_pct.

    For level='student': per subject.
    For all other levels: per student.
    """
    if scores_df.empty:
        return pd.DataFrame()

    if level == "student":
        key = "subject_id"
        score_grp = scores_df.groupby(key).agg(
            total_score=("score", "sum"), total_max=("max_score", "sum")
        ).reset_index()
        score_grp["progress_pct"] = (
            score_grp["total_score"] / score_grp["total_max"].replace(0, float("nan")) * 100
        ).round(1)

        if not attendance_df.empty:
            att_grp = attendance_df.groupby(key).agg(
                present=("is_present", "sum"), total=("is_present", "count")
            ).reset_index()
            att_grp["att_pct"] = (
                att_grp["present"] / att_grp["total"].replace(0, float("nan")) * 100
            ).round(1)
            result = score_grp.merge(att_grp[[key, "att_pct"]], on=key, how="left")
        else:
            result = score_grp.copy()
            result["att_pct"] = None

        if subject_names_df is not None and not subject_names_df.empty:
            result = result.merge(subject_names_df, on="subject_id", how="left")
            result["label"] = result["subject_name"].fillna(result["subject_id"].astype(str))
        else:
            result["label"] = result["subject_id"].astype(str)
    else:
        key = "user_id"
        score_grp = scores_df.groupby(key).agg(
            total_score=("score", "sum"), total_max=("max_score", "sum")
        ).reset_index()
        score_grp["progress_pct"] = (
            score_grp["total_score"] / score_grp["total_max"].replace(0, float("nan")) * 100
        ).round(1)

        if not attendance_df.empty:
            att_grp = attendance_df.groupby(key).agg(
                present=("is_present", "sum"), total=("is_present", "count")
            ).reset_index()
            att_grp["att_pct"] = (
                att_grp["present"] / att_grp["total"].replace(0, float("nan")) * 100
            ).round(1)
            result = score_grp.merge(att_grp[[key, "att_pct"]], on=key, how="left")
        else:
            result = score_grp.copy()
            result["att_pct"] = None

        result["label"] = result["user_id"].astype(str)

    return result.dropna(subset=["progress_pct"]).reset_index(drop=True)


def build_academic_kpis(
    cumulative_df: pd.DataFrame,
    scores_df: pd.DataFrame,
    attendance_df: pd.DataFrame,
    risk_df: pd.DataFrame,
    velocity_df: pd.DataFrame,
) -> dict:
    kpis: dict = {}

    if not cumulative_df.empty:
        valid = cumulative_df.dropna(subset=["cum_score"])
        if not valid.empty:
            last = valid.iloc[-1]
            kpis["cum_score"]    = round(float(last["cum_score"]), 1)
            kpis["cum_max"]      = round(float(last["cum_max"]), 1)
            kpis["progress_pct"] = (
                round(float(last["progress_pct"]), 1)
                if pd.notna(last.get("progress_pct")) else None
            )

    if not scores_df.empty:
        total_s = scores_df["score"].sum()
        total_m = scores_df["max_score"].sum()
        kpis["overall_progress"] = _safe_div(total_s, total_m)
        kpis["pass_rate"] = round(scores_df["is_passed"].mean() * 100, 1)

    if not attendance_df.empty:
        kpis["avg_attendance"] = round(attendance_df["is_present"].mean() * 100, 1)

    if not risk_df.empty:
        kpis["risk_share"] = float(risk_df["risk_pct"].iloc[-1])

    if not velocity_df.empty:
        kpis["avg_weekly_velocity"] = round(float(velocity_df["avg_weekly_score"].mean()), 1)

    return kpis


# ── Устаревшие методы (используются usage/correlation) ────────────────────────

class AcademicService:
    """Legacy wrapper kept for usage/correlation pages."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def score_burnup_velocity(self, start, end, rolling=7, faculty_id=None, group_id=None):
        from app.core.time_aggregation import fill_date_gaps, add_rolling_avg
        raw = pg.daily_score_raw(self.engine, start, end, faculty_id, group_id)
        if raw.empty:
            return pd.DataFrame()
        raw = fill_date_gaps(raw, "date", ["avg_score", "avg_max_score"])
        raw["avg_score"]     = raw["avg_score"].fillna(0)
        raw["avg_max_score"] = raw["avg_max_score"].fillna(0)
        raw["cumulative_score"] = raw["avg_score"].cumsum().round(2)
        raw["cumulative_max"]   = raw["avg_max_score"].cumsum().round(2)
        raw["progress_pct"]  = (
            raw["cumulative_score"] / raw["cumulative_max"].replace(0, float("nan")) * 100
        ).round(2)
        raw["velocity"] = raw["avg_score"].rolling(window=rolling, min_periods=1).mean().round(3)
        raw = add_rolling_avg(raw, "date", "cumulative_score", windows=[rolling])
        raw = add_rolling_avg(raw, "date", "progress_pct",    windows=[rolling])
        return raw.reset_index(drop=True)

    def score_distribution_weekly(self, start, end, group_id=None):
        return pg.weekly_score_distribution(self.engine, start, end, group_id)

    def momentum(self, start, end, rolling=7, faculty_id=None, group_id=None):
        from app.core.time_aggregation import fill_date_gaps, compute_momentum
        gpa = pg.daily_gpa(self.engine, start, end, faculty_id, group_id)
        att = pg.daily_attendance(self.engine, start, end, faculty_id, group_id)
        if gpa.empty:
            return pd.DataFrame()
        gpa = gpa.rename(columns={"avg_score_pct": "gpa"})
        att = att.rename(columns={"attendance_pct": "attendance"})
        df  = gpa[["date", "gpa"]].merge(att[["date", "attendance"]], on="date", how="outer")
        df  = fill_date_gaps(df, "date", ["gpa", "attendance"])
        df  = compute_momentum(df, "date", "gpa",        smooth_window=rolling)
        df  = compute_momentum(df, "date", "attendance", smooth_window=rolling)
        return df.reset_index(drop=True)

    def seasonal_waves(self, start, end, group_id=None, faculty_id=None):
        from app.core.time_aggregation import fill_date_gaps
        gpa = pg.daily_gpa(self.engine, start, end, faculty_id, group_id)
        att = pg.daily_attendance(self.engine, start, end, faculty_id, group_id)
        prt = pg.daily_pass_rate(self.engine, start, end, group_id)
        if gpa.empty:
            return pd.DataFrame()
        gpa = gpa.rename(columns={"avg_score_pct": "gpa"})
        att = att.rename(columns={"attendance_pct": "attendance"})
        df  = (
            gpa[["date", "gpa"]]
            .merge(att[["date", "attendance"]], on="date", how="outer")
            .merge(prt[["date", "pass_rate"]],  on="date", how="outer")
        )
        df["date"] = pd.to_datetime(df["date"])
        df["week_of_year"] = df["date"].dt.isocalendar().week.astype(int)
        return (
            df.groupby("week_of_year")
            .agg(
                avg_score_pct=("gpa",        "mean"),
                attendance_pct=("attendance", "mean"),
                pass_rate=("pass_rate",       "mean"),
            )
            .reset_index()
            .sort_values("week_of_year")
        )
