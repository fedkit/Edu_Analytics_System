"""Reusable Plotly chart builders."""

from __future__ import annotations

from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

PLOTLY_CONFIG = {"displayModeBar": True, "toImageButtonOptions": {"format": "png"}}

PALETTE = px.colors.qualitative.Set2


# ── Line / Area ───────────────────────────────────────────────────────────────

def line_chart(
    df: pd.DataFrame,
    x: str,
    y: str | list[str],
    title: str = "",
    y_label: str = "",
    prev_y: str | None = None,
    ma_col: str | None = None,
    anomaly_col: str | None = None,
    area: bool = False,
) -> go.Figure:
    ys = [y] if isinstance(y, str) else y
    fig = go.Figure()

    for i, col in enumerate(ys):
        mode = "lines" if area else "lines"
        fig.add_trace(
            go.Scatter(
                x=df[x], y=df[col],
                mode=mode,
                name=col,
                line=dict(color=PALETTE[i % len(PALETTE)], width=2.5),
                fill="tozeroy" if area else None,
                fillcolor=PALETTE[i % len(PALETTE)].replace(")", ",0.15)").replace("rgb", "rgba")
                if area else None,
            )
        )

    if prev_y and prev_y in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df[x], y=df[prev_y],
                mode="lines",
                name="Прошлый период",
                line=dict(color="#aaaaaa", width=1.5, dash="dash"),
            )
        )

    if ma_col and ma_col in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df[x], y=df[ma_col],
                mode="lines",
                name="Скольз. среднее",
                line=dict(color="#f39c12", width=1.5, dash="dot"),
            )
        )

    if anomaly_col and anomaly_col in df.columns:
        anomalies = df[df[anomaly_col]]
        if not anomalies.empty:
            fig.add_trace(
                go.Scatter(
                    x=anomalies[x], y=anomalies[ys[0]],
                    mode="markers",
                    name="Аномалия",
                    marker=dict(color="red", size=8, symbol="x"),
                )
            )

    fig.update_layout(
        title=title,
        xaxis_title=x,
        yaxis_title=y_label or (ys[0] if len(ys) == 1 else ""),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=20, t=50, b=40),
    )
    return fig


# ── Bar chart ─────────────────────────────────────────────────────────────────

def bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str | list[str],
    title: str = "",
    horizontal: bool = False,
    stacked: bool = False,
    color_col: str | None = None,
) -> go.Figure:
    ys = [y] if isinstance(y, str) else y

    if color_col:
        fig = px.bar(df, x=x, y=ys[0], color=color_col, title=title,
                     orientation="h" if horizontal else "v",
                     barmode="stack" if stacked else "group",
                     color_discrete_sequence=PALETTE)
    else:
        fig = go.Figure()
        for i, col in enumerate(ys):
            fig.add_trace(
                go.Bar(
                    x=df[x] if not horizontal else df[col],
                    y=df[col] if not horizontal else df[x],
                    name=col,
                    marker_color=PALETTE[i % len(PALETTE)],
                    orientation="h" if horizontal else "v",
                )
            )
        fig.update_layout(
            barmode="stack" if stacked else "group",
            title=title,
            hovermode="x unified",
        )

    fig.update_layout(margin=dict(l=40, r=20, t=50, b=40))
    return fig


# ── Heatmap ───────────────────────────────────────────────────────────────────

def heatmap(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    value_col: str,
    title: str = "",
    x_labels: list[str] | None = None,
    y_labels: list[str] | None = None,
    colorscale: str = "Blues",
) -> go.Figure:
    pivot = df.pivot_table(index=y_col, columns=x_col, values=value_col, aggfunc="sum").fillna(0)
    fig = go.Figure(
        go.Heatmap(
            z=pivot.values,
            x=x_labels or [str(c) for c in pivot.columns],
            y=y_labels or [str(r) for r in pivot.index],
            colorscale=colorscale,
            hoverongaps=False,
            text=pivot.values.round(1),
            texttemplate="%{text}",
        )
    )
    fig.update_layout(title=title, margin=dict(l=60, r=20, t=50, b=40))
    return fig


# ── Funnel ────────────────────────────────────────────────────────────────────

def funnel_chart(df: pd.DataFrame, label_col: str, value_col: str, title: str = "") -> go.Figure:
    fig = go.Figure(
        go.Funnel(
            y=df[label_col],
            x=df[value_col],
            textinfo="value+percent initial",
            marker=dict(color=PALETTE[: len(df)]),
        )
    )
    fig.update_layout(title=title, margin=dict(l=40, r=20, t=50, b=40))
    return fig


# ── Scatter ───────────────────────────────────────────────────────────────────

def scatter_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    color_col: str | None = None,
    size_col: str | None = None,
    title: str = "",
    trendline: bool = True,
) -> go.Figure:
    fig = px.scatter(
        df, x=x, y=y,
        color=color_col,
        size=size_col,
        trendline="ols" if trendline else None,
        title=title,
        color_discrete_sequence=PALETTE,
        opacity=0.65,
    )
    fig.update_layout(margin=dict(l=40, r=20, t=50, b=40))
    return fig


# ── Pie / Donut ───────────────────────────────────────────────────────────────

def pie_chart(
    df: pd.DataFrame, labels_col: str, values_col: str,
    title: str = "", hole: float = 0.4
) -> go.Figure:
    fig = go.Figure(
        go.Pie(
            labels=df[labels_col],
            values=df[values_col],
            hole=hole,
            textinfo="label+percent",
            marker=dict(colors=PALETTE),
        )
    )
    fig.update_layout(title=title, margin=dict(l=20, r=20, t=50, b=20))
    return fig


# ── Sankey ────────────────────────────────────────────────────────────────────

def sankey_chart(
    transitions: pd.DataFrame,
    from_col: str = "from_page",
    to_col: str = "to_page",
    value_col: str = "transitions",
    title: str = "Навигация пользователей",
) -> go.Figure:
    all_nodes = list(
        pd.concat([transitions[from_col], transitions[to_col]]).unique()
    )
    node_idx = {n: i for i, n in enumerate(all_nodes)}
    fig = go.Figure(
        go.Sankey(
            node=dict(label=all_nodes, color=PALETTE[: len(all_nodes)] * 10),
            link=dict(
                source=[node_idx[r] for r in transitions[from_col]],
                target=[node_idx[r] for r in transitions[to_col]],
                value=transitions[value_col].tolist(),
            ),
        )
    )
    fig.update_layout(title=title, margin=dict(l=40, r=20, t=50, b=40))
    return fig


# ── Cohort heatmap ────────────────────────────────────────────────────────────

def cohort_heatmap(retention_matrix: pd.DataFrame, title: str = "Cohort Retention") -> go.Figure:
    if retention_matrix.empty:
        return go.Figure()

    z = retention_matrix.values
    y_labels = [str(d.date()) if hasattr(d, "date") else str(d) for d in retention_matrix.index]
    x_labels = [f"Неделя {c}" for c in retention_matrix.columns]

    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=x_labels,
            y=y_labels,
            colorscale="Blues",
            text=[[f"{v:.0f}%" if v == v else "" for v in row] for row in z],
            texttemplate="%{text}",
            zmin=0, zmax=100,
            hoverongaps=False,
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Неделя с момента первого визита",
        yaxis_title="Когорта (неделя)",
        margin=dict(l=80, r=20, t=60, b=50),
        height=max(300, 30 * len(y_labels)),
    )
    return fig


# ── Correlation matrix ────────────────────────────────────────────────────────

def correlation_matrix_chart(corr_df: pd.DataFrame, title: str = "Матрица корреляций") -> go.Figure:
    fig = go.Figure(
        go.Heatmap(
            z=corr_df.values,
            x=corr_df.columns.tolist(),
            y=corr_df.index.tolist(),
            colorscale="RdBu",
            zmid=0,
            text=corr_df.round(2).values,
            texttemplate="%{text}",
            zmin=-1, zmax=1,
        )
    )
    fig.update_layout(
        title=title,
        margin=dict(l=120, r=20, t=60, b=80),
        height=450,
    )
    return fig


# ── Box plot ──────────────────────────────────────────────────────────────────

def box_plot(
    df: pd.DataFrame, x: str, y: str, title: str = "", color_col: str | None = None
) -> go.Figure:
    fig = px.box(df, x=x, y=y, color=color_col, title=title,
                 color_discrete_sequence=PALETTE)
    fig.update_layout(margin=dict(l=40, r=20, t=50, b=40))
    return fig
