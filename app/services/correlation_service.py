"""Сервис корреляционной аналитики: temporal relationships между поведением и обучением."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
from clickhouse_connect.driver.client import Client
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sqlalchemy.engine import Engine

from app.core.time_aggregation import add_rolling_avg, fill_date_gaps, normalize_0_100
from app.queries import clickhouse_queries as ch_q
from app.queries import postgres_queries as pg


def _corr(s1: pd.Series, s2: pd.Series, method: str = "pearson") -> float:
    df = pd.DataFrame({"a": s1, "b": s2}).dropna()
    if len(df) < 5:
        return float("nan")
    if method == "spearman":
        r, _ = stats.spearmanr(df["a"], df["b"])
    else:
        r, _ = stats.pearsonr(df["a"], df["b"])
    return round(float(r), 3) if not np.isnan(r) else float("nan")


def _rolling_corr(s1: pd.Series, s2: pd.Series, window: int) -> pd.Series:
    return s1.rolling(window=window, min_periods=max(5, window // 3)).corr(s2).round(3)


def _rolling_spearman(s1: pd.Series, s2: pd.Series, window: int) -> pd.Series:
    # Global rank-transform → rolling Pearson of ranks ≈ rolling Spearman
    r1 = s1.rank(method="average")
    r2 = s2.rank(method="average")
    return r1.rolling(window=window, min_periods=max(5, window // 3)).corr(r2).round(3)


BEHAVIOR_COLS = [
    "session_count", "sessions_per_week", "event_count",
    "avg_duration_min", "active_days", "unique_pages", "events_per_session",
]
ACADEMIC_COLS = [
    "progress_pct", "pass_rate", "att_pct",
]
CORR_LABELS: dict[str, str] = {
    "session_count":    "Сессии (всего)",
    "sessions_per_week":"Сессий в неделю",
    "event_count":      "События",
    "avg_duration_min": "Длит. сессии (мин)",
    "active_days":      "Активных дней",
    "unique_pages":     "Уникальных страниц",
    "events_per_session":"Событий/сессию",
    "progress_pct":     "Прогресс (%)",
    "pass_rate":        "Pass rate (%)",
    "att_pct":          "Посещаемость (%)",
    "risk_flag":        "Риск отставания",
    "total_score":      "Набрано баллов",
}


class CorrelationService:
    def __init__(self, engine: Engine, ch: Client) -> None:
        self.engine = engine
        self.ch = ch

    # ── Per-user combined data ────────────────────────────────────────────────

    def combined_per_user(
        self,
        start: date,
        end: date,
        group_id: int | None = None,
        faculty_id: int | None = None,
        course: int | None = None,
    ) -> pd.DataFrame:
        """Join behavioral (CH) + academic (PG) data per student."""
        beh  = ch_q.per_user_behavior_extended(self.ch, start, end)
        acad = pg.per_user_academic_extended(self.engine, start, end, group_id, faculty_id, course)

        if beh.empty or acad.empty:
            return pd.DataFrame()

        df = beh.merge(acad, on="user_id", how="inner")
        return df.reset_index(drop=True)

    # ── Daily combined for rolling correlations ───────────────────────────────

    def daily_combined(
        self,
        start: date,
        end: date,
        group_id: int | None = None,
        faculty_id: int | None = None,
    ) -> pd.DataFrame:
        """Daily PG + CH metrics merged."""
        gpa = pg.daily_gpa(self.engine, start, end, faculty_id, group_id).rename(
            columns={"avg_score_pct": "gpa"}
        )
        att = pg.daily_attendance(self.engine, start, end, faculty_id, group_id).rename(
            columns={"attendance_pct": "attendance"}
        )
        prt = pg.daily_pass_rate(self.engine, start, end, group_id).rename(
            columns={"pass_rate": "pass_rate"}
        )
        beh = ch_q.daily_behavior_intensity(self.ch, start, end)

        if gpa.empty or beh.empty:
            return pd.DataFrame()

        acad = (
            gpa[["date", "gpa"]]
            .merge(att[["date", "attendance"]], on="date", how="outer")
            .merge(prt[["date", "pass_rate"]],  on="date", how="outer")
        )
        acad["date"] = pd.to_datetime(acad["date"])
        beh["date"]  = pd.to_datetime(beh["date"])

        df = acad.merge(
            beh[["date", "dau", "sessions", "avg_duration_min", "events",
                 "sessions_per_user", "events_per_session"]],
            on="date", how="inner",
        ).sort_values("date")

        fill_cols = ["gpa", "attendance", "pass_rate",
                     "dau", "sessions", "avg_duration_min", "events"]
        df = fill_date_gaps(df, "date", fill_cols)
        return df.reset_index(drop=True)

    # ── Correlation matrix ────────────────────────────────────────────────────

    def correlation_matrix(
        self,
        per_user_df: pd.DataFrame,
        method: str = "pearson",
    ) -> pd.DataFrame:
        """Pairwise correlation matrix of behavioral + academic metrics."""
        cols = [c for c in BEHAVIOR_COLS + ACADEMIC_COLS + ["risk_flag"]
                if c in per_user_df.columns]
        if len(cols) < 3:
            return pd.DataFrame()

        sub = per_user_df[cols].apply(pd.to_numeric, errors="coerce")
        if method == "spearman":
            mat = sub.corr(method="spearman")
        else:
            mat = sub.corr(method="pearson")
        return mat.round(3)

    # ── Scatter: activity vs progress ─────────────────────────────────────────

    def scatter_data(
        self,
        per_user_df: pd.DataFrame,
        x_col: str = "sessions_per_week",
        y_col: str = "progress_pct",
    ) -> pd.DataFrame:
        """Scatter data with regression stats and risk zone labels."""
        needed = [x_col, y_col, "user_id"]
        if not all(c in per_user_df.columns for c in [x_col, y_col]):
            return pd.DataFrame()

        df = per_user_df[[c for c in needed if c in per_user_df.columns]].dropna(
            subset=[x_col, y_col]
        ).copy()

        if df.empty:
            return pd.DataFrame()

        # Risk zone colour
        def _zone(p: float) -> str:
            if p >= 80: return "Хорошо"
            if p >= 60: return "Нормально"
            if p >= 40: return "Риск"
            return "Критично"

        if "progress_pct" in df.columns:
            df["zone"] = df["progress_pct"].apply(_zone)
        else:
            df["zone"] = "Нормально"

        if len(df) >= 5:
            slope, intercept, r, p, _ = stats.linregress(df[x_col], df[y_col])
            df.attrs.update({
                "slope": round(slope, 4),
                "intercept": round(intercept, 2),
                "r_value": round(r, 3),
                "p_value": round(p, 4),
            })
        return df.reset_index(drop=True)

    # ── Lag analysis (weekly granularity) ─────────────────────────────────────

    def lag_analysis_weekly(
        self,
        start: date,
        end: date,
        predictor: str = "sessions",
        target: str = "progress",
        max_lag: int = 4,
        group_id: int | None = None,
        faculty_id: int | None = None,
        method: str = "pearson",
    ) -> pd.DataFrame:
        """corr(target[t+lag], predictor[t]) for lag 0..max_lag weeks."""
        acad = pg.weekly_academic_agg(self.engine, start, end, group_id, faculty_id)
        beh  = ch_q.weekly_behavior_agg(self.ch, start, end)

        if acad.empty or beh.empty:
            return pd.DataFrame()

        acad["week"] = pd.to_datetime(acad["week"])
        beh["week"]  = pd.to_datetime(beh["week"])

        target_col_map = {
            "progress":   "avg_score_pct",
            "pass_rate":  "pass_rate",
            "attendance": "attendance_pct",
        }
        predictor_col_map = {
            "sessions":     "sessions",
            "dau":          "dau",
            "avg_duration": "avg_duration_min",
            "events":       "events",
        }

        t_col = target_col_map.get(target, "avg_score_pct")
        p_col = predictor_col_map.get(predictor, "sessions")

        df = acad.merge(beh, on="week", how="inner").sort_values("week")
        if t_col not in df.columns or p_col not in df.columns or len(df) < 6:
            return pd.DataFrame()

        rows = []
        for lag in range(0, max_lag + 1):
            shifted_predictor = df[p_col].shift(lag)
            r = _corr(df[t_col], shifted_predictor, method)
            rows.append({"lag_weeks": lag, "lag_label": f"+{lag} нед.", "correlation": r})
        return pd.DataFrame(rows)

    # ── Risk correlations ──────────────────────────────────────────────────────

    def risk_correlations(
        self,
        per_user_df: pd.DataFrame,
        method: str = "pearson",
    ) -> pd.DataFrame:
        """Correlation of each behavioral metric with risk status (progress < 60%)."""
        if per_user_df.empty or "risk_flag" not in per_user_df.columns:
            return pd.DataFrame()

        rows = []
        for col in BEHAVIOR_COLS:
            if col not in per_user_df.columns:
                continue
            r = _corr(per_user_df["risk_flag"], per_user_df[col], method)
            if not np.isnan(r):
                rows.append({
                    "metric":      CORR_LABELS.get(col, col),
                    "correlation": r,
                    "abs_corr":    abs(r),
                })

        if not rows:
            return pd.DataFrame()

        return (
            pd.DataFrame(rows)
            .sort_values("abs_corr", ascending=False)
            .reset_index(drop=True)
        )

    # ── Rolling correlations time series ──────────────────────────────────────

    def rolling_correlations(
        self,
        start: date,
        end: date,
        window: int = 30,
        group_id: int | None = None,
        faculty_id: int | None = None,
    ) -> pd.DataFrame:
        df = self.daily_combined(start, end, group_id, faculty_id)
        if df.empty or len(df) < window:
            return pd.DataFrame()

        df["corr_gpa_sessions"] = _rolling_corr(df["gpa"], df["sessions"], window)
        df["corr_gpa_dau"]      = _rolling_corr(df["gpa"], df["dau"],      window)
        df["corr_att_sessions"] = _rolling_corr(df["attendance"], df["sessions"], window)
        df["corr_gpa_duration"] = _rolling_corr(df["gpa"], df["avg_duration_min"], window)

        df["scorr_gpa_sessions"] = _rolling_spearman(df["gpa"], df["sessions"], window)
        df["scorr_gpa_dau"]      = _rolling_spearman(df["gpa"], df["dau"],      window)
        df["scorr_att_sessions"] = _rolling_spearman(df["attendance"], df["sessions"], window)
        df["scorr_gpa_duration"] = _rolling_spearman(df["gpa"], df["avg_duration_min"], window)

        corr_cols = ["corr_gpa_sessions", "corr_gpa_dau",
                     "corr_att_sessions", "corr_gpa_duration"]
        scorr_cols = ["scorr_gpa_sessions", "scorr_gpa_dau",
                      "scorr_att_sessions", "scorr_gpa_duration"]
        df["coupling_index"] = df[corr_cols].abs().mean(axis=1).round(3)
        df = add_rolling_avg(df, "date", "coupling_index", windows=[7])

        return df[["date"] + corr_cols + scorr_cols + ["coupling_index", "coupling_index_ma7"]].reset_index(drop=True)

    # ── Page impact analysis ───────────────────────────────────────────────────

    def page_impact(
        self,
        start: date,
        end: date,
        per_user_academic: pd.DataFrame,
        method: str = "pearson",
    ) -> pd.DataFrame:
        """Correlation of page_section visit count with academic progress."""
        page_beh = ch_q.per_user_page_behavior(self.ch, start, end)
        if page_beh.empty or per_user_academic.empty:
            return pd.DataFrame()

        page_wide = page_beh.pivot_table(
            index="user_id", columns="page_section", values="visits",
            aggfunc="sum", fill_value=0,
        ).reset_index()

        df = page_wide.merge(
            per_user_academic[["user_id", "progress_pct"]].dropna(),
            on="user_id", how="inner",
        )
        if df.empty:
            return pd.DataFrame()

        sections = [c for c in df.columns if c not in ("user_id", "progress_pct")]
        rows = []
        for sec in sections:
            r = _corr(df["progress_pct"], df[sec], method)
            if not np.isnan(r):
                rows.append({"section": sec, "correlation": r, "abs_corr": abs(r)})

        if not rows:
            return pd.DataFrame()

        return (
            pd.DataFrame(rows)
            .sort_values("abs_corr", ascending=False)
            .reset_index(drop=True)
        )

    # ── Behavioral segmentation (k-means) ────────────────────────────────────

    def behavioral_segments(
        self,
        per_user_df: pd.DataFrame,
        n_clusters: int = 4,
    ) -> pd.DataFrame:
        """K-means clustering on behavioral + academic metrics."""
        feature_cols = [c for c in [
            "sessions_per_week", "avg_duration_min", "active_days",
            "progress_pct", "att_pct",
        ] if c in per_user_df.columns]

        if len(feature_cols) < 3 or len(per_user_df) < n_clusters * 3:
            return pd.DataFrame()

        X = per_user_df[feature_cols].copy()
        X = X.fillna(X.median())

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        k = min(n_clusters, len(per_user_df))
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X_scaled)

        df = per_user_df[feature_cols + ["user_id"]].copy()
        df["cluster"] = labels

        # Label clusters based on engagement + progress
        centroids = pd.DataFrame(
            scaler.inverse_transform(km.cluster_centers_), columns=feature_cols
        )

        SEGMENT_NAMES = {
            (True, True):   "Активные отличники",
            (True, False):  "Активные, но отстают",
            (False, True):  "Пассивные, но успевают",
            (False, False): "Пассивные и отстают",
        }
        if "sessions_per_week" in centroids.columns and "progress_pct" in centroids.columns:
            med_s = centroids["sessions_per_week"].median()
            med_p = centroids["progress_pct"].median()
            cluster_names = {}
            for i, row in centroids.iterrows():
                key = (row["sessions_per_week"] >= med_s, row["progress_pct"] >= med_p)
                cluster_names[i] = SEGMENT_NAMES.get(key, f"Кластер {i+1}")
            df["segment"] = df["cluster"].map(cluster_names)
        else:
            df["segment"] = df["cluster"].apply(lambda c: f"Кластер {c+1}")

        return df.reset_index(drop=True)

    # ── Early warning ─────────────────────────────────────────────────────────

    def early_warning(
        self,
        start: date,
        end: date,
        group_id: int | None = None,
        faculty_id: int | None = None,
    ) -> pd.DataFrame:
        """Students with declining activity trend + low/worsening progress."""
        weekly_beh  = ch_q.per_user_weekly_behavior(self.ch, start, end)
        weekly_acad = pg.per_user_weekly_academic(self.engine, start, end, group_id, faculty_id)

        if weekly_beh.empty or weekly_acad.empty:
            return pd.DataFrame()

        weekly_beh["week"]  = pd.to_datetime(weekly_beh["week"])
        weekly_acad["week"] = pd.to_datetime(weekly_acad["week"])

        df = weekly_beh.merge(weekly_acad, on=["user_id", "week"], how="inner")
        if df.empty:
            return pd.DataFrame()

        # Scope filter via inner join (only users with academic data in scope)
        results = []
        for uid, grp in df.groupby("user_id"):
            grp = grp.sort_values("week")
            if len(grp) < 3:
                continue

            # Linear trend of sessions over time
            x = np.arange(len(grp))
            if grp["sessions"].std() > 0:
                s_slope, _, _, _, _ = stats.linregress(x, grp["sessions"].fillna(0))
            else:
                s_slope = 0.0

            # Cumulative progress at last week
            total_score = grp["weekly_score"].sum()
            total_max   = grp["weekly_max"].sum()
            progress = (total_score / total_max * 100) if total_max > 0 else None

            if s_slope < -0.3 and progress is not None and progress < 70:
                results.append({
                    "user_id":          uid,
                    "sessions_trend":   round(s_slope, 2),
                    "current_progress": round(progress, 1),
                    "last_week_sessions": int(grp["sessions"].iloc[-1]),
                    "weeks_tracked":    len(grp),
                })

        if not results:
            return pd.DataFrame()

        out = pd.DataFrame(results).sort_values("current_progress")

        # Add user names if possible
        try:
            uids = out["user_id"].tolist()
            names = pg._q(
                self.engine,
                "SELECT user_id, surname || ' ' || first_name AS name FROM edu.\"user\" "
                "WHERE user_id = ANY(:uids)",
                {"uids": uids},
            )
            out = out.merge(names, on="user_id", how="left")
        except Exception:
            out["name"] = out["user_id"].astype(str)

        return out.reset_index(drop=True)

    # ── Dual time series ──────────────────────────────────────────────────────

    def dual_timeseries(
        self,
        start: date,
        end: date,
        rolling: int = 7,
        group_id: int | None = None,
        faculty_id: int | None = None,
    ) -> pd.DataFrame:
        df = self.daily_combined(start, end, group_id, faculty_id)
        if df.empty:
            return pd.DataFrame()

        df["gpa_norm"]      = normalize_0_100(df["gpa"])
        df["sessions_norm"] = normalize_0_100(df["sessions"])
        df = add_rolling_avg(df, "date", "gpa_norm",      windows=[rolling])
        df = add_rolling_avg(df, "date", "sessions_norm", windows=[rolling])
        return df[["date", "gpa", "sessions", "gpa_norm", "sessions_norm",
                   f"gpa_norm_ma{rolling}", f"sessions_norm_ma{rolling}"]].reset_index(drop=True)
