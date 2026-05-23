"""KPI card component rendered via st.metric + sparkline."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.analytics.kpi import KPI


def render_kpi_card(kpi: KPI, sparkline_data: pd.Series | None = None) -> None:
    delta_str, color = kpi.delta
    st.metric(
        label=f"{kpi.icon} {kpi.label}",
        value=kpi.formatted_value,
        delta=delta_str,
    )
    if sparkline_data is not None and not sparkline_data.empty:
        fig = _build_sparkline(sparkline_data, color)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _build_sparkline(data: pd.Series, color: str) -> go.Figure:
    fig = go.Figure(
        go.Scatter(
            y=data,
            mode="lines",
            line=dict(color=color, width=2),
            fill="tozeroy",
            fillcolor=color.replace(")", ", 0.15)").replace("rgb", "rgba"),
        )
    )
    fig.update_layout(
        height=60,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def render_kpi_row(kpis: list[KPI], sparklines: dict[str, pd.Series] | None = None) -> None:
    """Render a row of KPI cards (up to 5 per row)."""
    per_row = 5
    for i in range(0, len(kpis), per_row):
        batch = kpis[i : i + per_row]
        cols = st.columns(len(batch))
        for col, kpi in zip(cols, batch):
            with col:
                sl = (sparklines or {}).get(kpi.label)
                render_kpi_card(kpi, sl)
