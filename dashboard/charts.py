"""
Plotly figure builders for the Superstore dashboard
===================================================
One theme for every chart. RFM segment colours run cool (good customers) to
warm (at risk) and passed a colour-blind separation check on white; every
segment is also labelled by name, so colour never carries meaning alone.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from rfm import SEGMENTS

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
FONT = "Source Sans, Source Sans Pro, Segoe UI, system-ui, sans-serif"
INK = "#1F2933"
MUTED = "#6B7780"
GRID = "#E6ECEE"
NAVY = "#0B3C49"
TEAL = "#0E6E78"
NEUTRAL = "#2A78D6"   # single-series marks
FAINT = "#C9D3D8"
LOSS = "#D03B3B"      # negative profit
SEG_COLOR = dict(zip(SEGMENTS, ["#2A78D6", "#1BAF7A", "#EDA100", "#E34948", "#6250D6"]))
SEQUENTIAL = [[0, "#EEF4FB"], [0.5, "#6DA7EC"], [1, "#104281"]]

pio.templates["superstore"] = go.layout.Template(layout=dict(
    font=dict(family=FONT, size=13, color=INK),
    paper_bgcolor="white", plot_bgcolor="white",
    colorway=list(SEG_COLOR.values()),
    margin=dict(l=8, r=16, t=12, b=8),
    xaxis=dict(gridcolor=GRID, linecolor=GRID, zeroline=False, ticks="",
               tickfont=dict(color=MUTED), title=dict(font=dict(color=MUTED, size=12)), automargin=True),
    yaxis=dict(gridcolor=GRID, linecolor=GRID, zeroline=False, ticks="",
               tickfont=dict(color=MUTED), title=dict(font=dict(color=MUTED, size=12)), automargin=True),
    hoverlabel=dict(bgcolor="white", bordercolor=GRID, font=dict(family=FONT, color=INK, size=13)),
    legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, title_text="", font=dict(color=INK)),
    barcornerradius=4,
    bargap=0.3,
))
pio.templates.default = "superstore"

PLOT_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"]}


def money(v):
    """$2.30M / $286K / $459 style."""
    a = abs(v)
    sign = "-" if v < 0 else ""
    if a >= 1e6:
        return f"{sign}${a / 1e6:.2f}M"
    if a >= 1e4:
        return f"{sign}${a / 1e3:.0f}K"
    if a >= 1e3:
        return f"{sign}${a / 1e3:.1f}K"
    return f"{sign}${a:,.0f}"


# ---------------------------------------------------------------------------
# Generic bars
# ---------------------------------------------------------------------------
def hbar(labels, values, colors, text, height=260, hover=None):
    """Horizontal bars, first label on top, value text just past the bar end.
    Handles negative values (text goes past the left end)."""
    values = list(values)
    fig = go.Figure(go.Bar(
        y=list(labels), x=values, orientation="h",
        marker=dict(color=colors, line=dict(width=0)),
        text=list(text), textposition="outside", cliponaxis=False,
        textfont=dict(color=INK, size=13),
        hovertemplate=hover or "%{y}: %{x:,.0f}<extra></extra>",
    ))
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(color=INK, size=13))
    longest = max((len(str(t)) for t in text), default=0)
    room = 1.2 + 0.035 * longest
    lo, hi = min(min(values, default=0), 0), max(max(values, default=0), 0)
    span = (hi - lo) or 1
    fig.update_xaxes(range=[lo - (span * (room - 1) if lo < 0 else 0), hi + span * (room - 1)], visible=False)
    fig.update_layout(height=height, bargap=0.35)
    return fig


def vbar(labels, values, text, color=NEUTRAL, height=300, hover=None, ytitle=None, prefix="$"):
    values = list(values)
    fig = go.Figure(go.Bar(
        x=[str(v) for v in labels], y=values, marker=dict(color=color, line=dict(width=0)),
        text=list(text), textposition="outside", cliponaxis=False, textfont=dict(color=INK, size=13),
        hovertemplate=hover or "%{x}: %{y:,.0f}<extra></extra>",
    ))
    fig.update_xaxes(type="category", showgrid=False, tickfont=dict(color=INK, size=13))
    fig.update_yaxes(range=[min(0, min(values) * 1.2), max(values) * 1.18], title=ytitle, tickprefix=prefix)
    fig.update_layout(height=height, bargap=0.4)
    return fig


# ---------------------------------------------------------------------------
# Sales
# ---------------------------------------------------------------------------
def trend(series, title, fmt, height=330, prefix="$"):
    """Line over time, 2px line, markers, peak labelled."""
    fig = go.Figure(go.Scatter(
        x=series.index, y=series.values, mode="lines+markers",
        line=dict(color=NEUTRAL, width=2), marker=dict(size=7, color=NEUTRAL, line=dict(color="white", width=1.5)),
        hovertemplate="%{x|%b %Y}: %{customdata}<extra></extra>", customdata=[fmt(v) for v in series.values],
    ))
    if len(series):
        peak = series.idxmax()
        fig.add_annotation(x=peak, y=series.max(), text=f"Peak {fmt(series.max())}", showarrow=False,
                           yshift=14, font=dict(color=INK, size=12))
    fig.update_yaxes(title=title, rangemode="tozero", tickprefix=prefix)
    fig.update_xaxes(showgrid=False)
    fig.update_layout(height=height, hovermode="x unified")
    return fig


def profit_bars(g, height=None):
    """Profit per group: blue = profit, red = loss."""
    g = g.sort_values(ascending=False)
    return hbar(g.index, g.values, [NEUTRAL if v >= 0 else LOSS for v in g.values], [money(v) for v in g.values],
                height=height or max(240, 26 * len(g) + 40), hover="%{y}: $%{x:,.0f}<extra></extra>")


def _on_dark(v, lo, hi):
    """True when a heatmap cell is dark enough to need white text."""
    return (v - lo) / ((hi - lo) or 1) >= 0.5


def heatmap(t, fmt, height=300):
    """Rows x columns table of values, darker = larger."""
    fig = go.Figure(go.Heatmap(
        z=t.values, x=list(t.columns), y=list(t.index), colorscale=SEQUENTIAL, xgap=2, ygap=2,
        colorbar=dict(thickness=10, outlinewidth=0, len=0.8, tickprefix="$"),
        hovertemplate="%{y} · %{x}: $%{z:,.0f}<extra></extra>",
    ))
    lo, hi = (np.nanmin(t.values), np.nanmax(t.values)) if t.size else (0, 1)
    for i, r in enumerate(t.index):
        for j, c in enumerate(t.columns):
            v = t.values[i, j]
            fig.add_annotation(x=c, y=r, text=fmt(v), showarrow=False,
                               font=dict(size=12, color="white" if _on_dark(v, lo, hi) else INK))
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(color=INK))
    fig.update_xaxes(side="top", showgrid=False, tickfont=dict(color=INK))
    fig.update_layout(height=height)
    return fig


# ---------------------------------------------------------------------------
# RFM
# ---------------------------------------------------------------------------
def segment_bars(summary, col, fmt, share_col=None, height=250):
    s = summary[col]
    text = [fmt(v) + (f"  ·  {p:.0%}" if share_col else "") for v, p in
            zip(s.values, summary[share_col] if share_col else s.values)]
    return hbar(s.index, s.values, [SEG_COLOR[x] for x in s.index], text, height=height,
                hover="%{y}: %{x:,.0f}<extra></extra>")


def score_distribution(rfm, height=280):
    """Customers per total RFM score (3-15), coloured by the segment the score falls in."""
    g = rfm.groupby(["RFM_Score", "RFM_Segment"], observed=True).size().reset_index(name="n")
    fig = go.Figure()
    for s in SEGMENTS:
        d = g[g["RFM_Segment"] == s]
        fig.add_trace(go.Bar(x=d["RFM_Score"], y=d["n"], name=s, marker=dict(color=SEG_COLOR[s]),
                             hovertemplate="Score %{x}: %{y} customers<extra>" + s + "</extra>"))
    fig.update_xaxes(dtick=1, title="RFM score (R + F + M)", showgrid=False)
    fig.update_yaxes(title="Customers")
    fig.update_layout(height=height, bargap=0.15, legend=dict(y=1.02))
    return fig


def rfm_scatter(rfm, highlight=None, height=420):
    """Recency vs Monetary, one dot per customer. One segment can be highlighted, the rest go grey."""
    fig = go.Figure()
    order = SEGMENTS if highlight is None else [s for s in SEGMENTS if s != highlight] + [highlight]
    for s in order:
        d = rfm[rfm["RFM_Segment"] == s]
        on = highlight is None or s == highlight
        fig.add_trace(go.Scatter(
            x=d["Recency"], y=d["Monetary"], mode="markers", name=s,
            marker=dict(size=8, color=SEG_COLOR[s] if on else FAINT, opacity=0.85 if on else 0.5,
                        line=dict(color="white", width=1)),
            customdata=d[["Customer Name", "Frequency", "RFM_Code"]],
            hovertemplate=("<b>%{customdata[0]}</b><br>Last order %{x} days ago<br>%{customdata[1]} orders · "
                           "$%{y:,.0f}<br>RFM %{customdata[2]}<extra>" + s + "</extra>"),
            showlegend=on,
        ))
    fig.update_xaxes(title="Recency: days since last order (lower = more recent)")
    fig.update_yaxes(title="Monetary: total sales (log scale)", type="log",
                     tickvals=[10, 100, 1000, 10000], ticktext=["$10", "$100", "$1K", "$10K"])
    fig.update_layout(height=height, legend=dict(y=1.02))
    return fig


def rf_grid(rfm, height=330):
    """R score x F score: customers in each cell, darker = more customers."""
    t = rfm.pivot_table(index="F", columns="R", values="Customer ID", aggfunc="count", fill_value=0)
    t = t.reindex(index=[5, 4, 3, 2, 1], columns=[1, 2, 3, 4, 5], fill_value=0)
    m = rfm.pivot_table(index="F", columns="R", values="Monetary", aggfunc="mean").reindex_like(t)
    fig = go.Figure(go.Heatmap(
        z=t.values, x=[f"R{c}" for c in t.columns], y=[f"F{r}" for r in t.index], colorscale=SEQUENTIAL,
        xgap=2, ygap=2, colorbar=dict(thickness=10, outlinewidth=0, len=0.8, title=dict(text="Customers", side="top")),
        customdata=np.nan_to_num(m.values), hovertemplate="%{y} · %{x}: %{z} customers<br>avg sales $%{customdata:,.0f}<extra></extra>",
    ))
    lo, hi = t.values.min(), t.values.max()
    for i, r in enumerate(t.index):
        for j, c in enumerate(t.columns):
            v = t.values[i, j]
            fig.add_annotation(x=f"R{c}", y=f"F{r}", text=str(v), showarrow=False,
                               font=dict(size=12, color="white" if _on_dark(v, lo, hi) else INK))
    fig.update_xaxes(title="Recency score (5 = bought most recently)", showgrid=False, side="bottom")
    fig.update_yaxes(title="Frequency score (5 = most orders)", showgrid=False)
    fig.update_layout(height=height)
    return fig
