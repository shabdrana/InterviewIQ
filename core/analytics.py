"""Plotly charts, styled for the dark navy UI."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .rubric import DIMENSIONS, LABELS

PURPLE, BLUE, CYAN, GREEN, AMBER, RED = "#8B6CFF", "#4C8DFF", "#22D3EE", "#34D399", "#FBBF24", "#F87171"
GRID = "rgba(139,151,199,.16)"
FONT = dict(family="Manrope, sans-serif", color="#C9D1F5", size=12)


def _theme(fig: go.Figure, height: int = 320, legend: bool = True) -> go.Figure:
    fig.update_layout(height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=FONT,
                      margin=dict(l=10, r=10, t=30, b=10), showlegend=legend,
                      legend=dict(orientation="h", y=-0.18, bgcolor="rgba(0,0,0,0)"),
                      hoverlabel=dict(bgcolor="#1A2347", bordercolor="#3A4680", font=dict(color="#E8ECFF")))
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=GRID)
    return fig


def _df(perf: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(perf)
    if not df.empty:
        df["n"] = range(1, len(df) + 1)
        df["label"] = df["n"].map(lambda i: f"#{i}")
    return df


def overall_trend(perf: list[dict]) -> go.Figure:
    df = _df(perf)
    fig = go.Figure()
    if not df.empty:
        fig.add_trace(go.Scatter(x=df["label"], y=df["overall"], mode="lines+markers", name="Overall",
                                 line=dict(color=PURPLE, width=3, shape="spline"), marker=dict(size=9, color=BLUE, line=dict(width=2, color="#0B1020")),
                                 fill="tozeroy", fillcolor="rgba(124,92,255,.12)",
                                 customdata=df[["interview_type", "domain"]].fillna("").values,
                                 hovertemplate="Attempt %{x}<br>%{y:.0f}/100<br>%{customdata[0]} %{customdata[1]}<extra></extra>"))
    fig.update_yaxes(range=[0, 100], title="Score")
    fig.update_xaxes(title="Interview attempt")
    return _theme(fig, legend=False)


def skill_lines(perf: list[dict]) -> go.Figure:
    df = _df(perf)
    fig, colors = go.Figure(), [PURPLE, BLUE, CYAN, GREEN, AMBER, RED]
    for d, c in zip(DIMENSIONS, colors):
        if not df.empty and df[d].notna().any():
            fig.add_trace(go.Scatter(x=df["label"], y=df[d], mode="lines+markers", name=LABELS[d], connectgaps=True,
                                     line=dict(color=c, width=2), marker=dict(size=6)))
    fig.update_yaxes(range=[0, 10], title="Score (0-10)")
    return _theme(fig, 340)


def technical_vs_behavioral(rows: list[dict]) -> go.Figure:
    """rows: answered conversation rows across sessions (category, overall)."""
    df = pd.DataFrame(rows)
    fig = go.Figure()
    if not df.empty:
        g = df.groupby("category")["overall"].mean().reindex(["technical", "behavioral", "hr", "general"]).dropna()
        names = {"technical": "Technical", "behavioral": "Behavioral", "hr": "HR", "general": "General"}
        fig.add_trace(go.Bar(x=[names[i] for i in g.index], y=g.values, marker=dict(color=[PURPLE, BLUE, CYAN, GREEN][:len(g)],
                                                                                   cornerradius=8),
                             text=[f"{v:.0f}" for v in g.values], textposition="outside", hovertemplate="%{x}: %{y:.1f}<extra></extra>"))
    fig.update_yaxes(range=[0, 105], title="Mean answer score")
    return _theme(fig, legend=False)


def radar(series: dict[str, dict]) -> go.Figure:
    """series: {name: {dimension: value}}. Dimensions that are None for every series are skipped."""
    dims = [d for d in DIMENSIONS if any(v.get(d) is not None for v in series.values())]
    fig = go.Figure()
    for (name, vals), c in zip(series.items(), [PURPLE, CYAN, AMBER]):
        r = [vals.get(d) or 0 for d in dims]
        fig.add_trace(go.Scatterpolar(r=r + r[:1], theta=[LABELS[d] for d in dims] + [LABELS[dims[0]]], name=name, fill="toself",
                                      line=dict(color=c, width=2), opacity=.85))
    fig.update_layout(polar=dict(bgcolor="rgba(0,0,0,0)", radialaxis=dict(range=[0, 10], gridcolor=GRID, linecolor=GRID, tickfont=dict(size=9)),
                                 angularaxis=dict(gridcolor=GRID, linecolor=GRID)))
    return _theme(fig, 360)


def improvement_areas(dims: dict) -> go.Figure:
    items = sorted(((LABELS[d], v) for d, v in dims.items() if v is not None), key=lambda x: x[1])
    fig = go.Figure(go.Bar(x=[v for _, v in items], y=[k for k, _ in items], orientation="h",
                           marker=dict(color=[RED if v < 5 else AMBER if v < 7 else GREEN for _, v in items], cornerradius=6),
                           text=[f"{v:.1f}" for _, v in items], textposition="outside"))
    fig.update_xaxes(range=[0, 10.5], title="Average (0-10)")
    return _theme(fig, 300, legend=False)


def score_compare(a: dict, b: dict, la: str, lb: str) -> go.Figure:
    dims = [d for d in DIMENSIONS if a.get(d) is not None or b.get(d) is not None]
    fig = go.Figure()
    fig.add_trace(go.Bar(name=la, x=[LABELS[d] for d in dims], y=[a.get(d) or 0 for d in dims], marker=dict(color=BLUE, cornerradius=5)))
    fig.add_trace(go.Bar(name=lb, x=[LABELS[d] for d in dims], y=[b.get(d) or 0 for d in dims], marker=dict(color=PURPLE, cornerradius=5)))
    fig.update_layout(barmode="group")
    fig.update_yaxes(range=[0, 10], title="Score (0-10)")
    return _theme(fig, 320)


def ai_vs_human_scatter(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 100], y=[0, 100], mode="lines", line=dict(color=GRID, dash="dash"), name="Perfect agreement", hoverinfo="skip"))
    if not df.empty:
        fig.add_trace(go.Scatter(x=df["h_overall"], y=df["a_overall"], mode="markers", name="Answers",
                                 marker=dict(size=11, color=PURPLE, line=dict(width=1.5, color="#0B1020")),
                                 hovertemplate="Human %{x:.0f}<br>AI %{y:.0f}<extra></extra>"))
    fig.update_xaxes(range=[0, 100], title="Human overall score")
    fig.update_yaxes(range=[0, 100], title="AI overall score")
    return _theme(fig, 360)


def difference_bars(df: pd.DataFrame) -> go.Figure:
    d = (df["a_overall"] - df["h_overall"]).round(1)
    fig = go.Figure(go.Bar(x=[f"A{i}" for i in df["answer_id"]], y=d, marker=dict(color=[AMBER if v > 0 else BLUE for v in d], cornerradius=4),
                           hovertemplate="%{x}: %{y:+.1f}<extra></extra>"))
    fig.update_yaxes(title="AI minus human (points)")
    return _theme(fig, 300, legend=False)
