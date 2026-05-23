"""Shared helper utilities."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional, Tuple

import pandas as pd


# ── Date range presets ────────────────────────────────────────────────────────

SEMESTER_BOUNDS: list[Tuple[date, date]] = [
    (date(2024, 2, 5), date(2024, 6, 30)),   # Spring 2024
    (date(2024, 9, 2), date(2025, 1, 31)),   # Fall 2024
    (date(2025, 2, 3), date(2025, 6, 29)),   # Spring 2025
]


def get_preset_dates(preset: str) -> Tuple[date, date]:
    today = date.today()
    match preset:
        case "today":
            return today, today
        case "yesterday":
            y = today - timedelta(days=1)
            return y, y
        case "last_7":
            return today - timedelta(days=6), today
        case "last_30":
            return today - timedelta(days=29), today
        case "last_90":
            return today - timedelta(days=89), today
        case "this_semester":
            for s, e in reversed(SEMESTER_BOUNDS):
                if s <= today:
                    return s, min(e, today)
            return today - timedelta(days=90), today
        case "prev_semester":
            for i, (s, e) in enumerate(reversed(SEMESTER_BOUNDS)):
                if s <= today and i > 0:
                    ps, pe = list(reversed(SEMESTER_BOUNDS))[i - 1]
                    return ps, pe
            return today - timedelta(days=180), today - timedelta(days=90)
        case _:
            return today - timedelta(days=29), today


def previous_period(start: date, end: date) -> Tuple[date, date]:
    """Return an equal-length period immediately before [start, end]."""
    span = (end - start).days + 1
    return start - timedelta(days=span), start - timedelta(days=1)


def fmt_delta(current: float, previous: float) -> Tuple[str, str]:
    """Return (formatted delta string, color)."""
    if previous == 0:
        return "—", "gray"
    pct = (current - previous) / abs(previous) * 100
    sign = "+" if pct >= 0 else ""
    color = "#2ecc71" if pct >= 0 else "#e74c3c"
    return f"{sign}{pct:.1f}%", color


def safe_div(a: float, b: float, default: float = 0.0) -> float:
    return a / b if b else default


def truncate_date(dt: pd.Series, granularity: str) -> pd.Series:
    """Truncate a datetime Series to the given granularity."""
    match granularity:
        case "hourly":
            return dt.dt.floor("h")
        case "daily":
            return dt.dt.floor("D")
        case "weekly":
            return dt.dt.to_period("W").dt.start_time
        case "monthly":
            return dt.dt.to_period("M").dt.start_time
        case "semester":
            def _sem(d: datetime) -> datetime:
                for s, e in SEMESTER_BOUNDS:
                    if s <= d.date() <= e:
                        return datetime(s.year, s.month, s.day)
                return datetime(d.year, 1, 1)
            return dt.apply(_sem)
        case _:
            return dt.dt.floor("D")


def human_number(n: float) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{n:.0f}"
