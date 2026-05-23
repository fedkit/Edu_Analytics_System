"""KPI computation: current value, previous period value, delta."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

import pandas as pd

from app.utils.helpers import fmt_delta, human_number, previous_period


@dataclass
class KPI:
    label: str
    value: float
    prev_value: float
    unit: str = ""
    precision: int = 1
    icon: str = ""

    @property
    def formatted_value(self) -> str:
        if self.unit == "%":
            return f"{self.value:.{self.precision}f}%"
        return human_number(self.value)

    @property
    def delta(self) -> tuple[str, str]:
        return fmt_delta(self.value, self.prev_value)

    @property
    def sparkline_color(self) -> str:
        delta_str, color = self.delta
        return color


def build_behavior_kpis(
    curr: dict, prev: dict
) -> list[KPI]:
    return [
        KPI("DAU", curr.get("dau", 0),   prev.get("dau", 0),   icon="👥"),
        KPI("WAU", curr.get("wau", 0),   prev.get("wau", 0),   icon="📅"),
        KPI("MAU", curr.get("mau", 0),   prev.get("mau", 0),   icon="📆"),
        KPI("Сессии", curr.get("total_sessions", 0), prev.get("total_sessions", 0), icon="🔗"),
        KPI("События", curr.get("total_events", 0), prev.get("total_events", 0), icon="⚡"),
        KPI(
            "Ср. длительность (мин)",
            round(curr.get("avg_duration_min", 0), 1),
            round(prev.get("avg_duration_min", 0), 1),
            icon="⏱",
            precision=1,
        ),
        KPI(
            "Сессий на пользователя",
            round(curr.get("sessions_per_user", 0), 2),
            round(prev.get("sessions_per_user", 0), 2),
            icon="📊",
            precision=2,
        ),
    ]


def build_academic_kpis(curr: dict, prev: dict) -> list[KPI]:
    return [
        KPI("Ср. балл (%)", round(curr.get("avg_score_pct", 0) or 0, 1),
            round(prev.get("avg_score_pct", 0) or 0, 1), unit="%", icon="🎓"),
        KPI("Pass Rate (%)", round(curr.get("pass_rate", 0) or 0, 1),
            round(prev.get("pass_rate", 0) or 0, 1), unit="%", icon="✅"),
        KPI("Провалено", curr.get("failed_count", 0) or 0,
            prev.get("failed_count", 0) or 0, icon="❌"),
        KPI("Посещаемость (%)", round(curr.get("avg_attendance", 0) or 0, 1),
            round(prev.get("avg_attendance", 0) or 0, 1), unit="%", icon="📋"),
        KPI("Активные студенты", curr.get("active_students", 0),
            prev.get("active_students", 0), icon="🧑‍🎓"),
    ]
