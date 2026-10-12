"""Plotly charts for the dashboard (REQ-014).

Rules (dataviz method):
- One series → one color (slot 1). Lines keep a fixed color per line, in master
  order, so a filter never repaints a line.
- Magnitude (heatmap) → one hue, light → dark.
- Thin marks, hairline grid, one y-axis, hover on every mark.
Palette validated with the dataviz validator (3 slots, all pairs, light and dark).
"""

import plotly.graph_objects as go

PALETTE = {
    "light": {
        "series": ["#2a78d6", "#eb6834", "#1baf7a"],
        "muted": "#898781",
        "grid": "#e1e0d9",
        "axis": "#c3c2b7",
        "text": "#5A6670",  # steel, from the page tokens
    },
    "dark": {
        "series": ["#3987e5", "#d95926", "#199e70"],
        "muted": "#898781",
        "grid": "#2c2c2a",
        "axis": "#383835",
        "text": "#c3c2b7",
    },
}
SEQUENTIAL_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def line_colors(lines, mode: str) -> dict[str, str]:
    """Fixed color per line, following the master list order (never the current ranking)."""
    series = PALETTE[mode]["series"]
    return {line: series[i % len(series)] for i, line in enumerate(sorted(lines))}


def _layout(fig: go.Figure, mode: str, height: int = 320, percent_axis: bool = False) -> go.Figure:
    colors = PALETTE[mode]
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
        bargap=0.45,
        barcornerradius=4,
        hoverlabel=dict(font_size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title_text=""),
        font=dict(color=colors["text"], family="Barlow, system-ui, sans-serif", size=13),
    )
    fig.update_xaxes(showgrid=False, linecolor=colors["axis"], title_text="")
    fig.update_yaxes(gridcolor=colors["grid"], gridwidth=1, zeroline=False, title_text="",
                     tickformat=".1%" if percent_axis else ",")
    return fig


def bar(categories, values, mode: str, hover_text=None, percent: bool = False,
        colors=None, horizontal: bool = True) -> go.Figure:
    """Single-series bar chart with the value on each bar (few bars only).

    Horizontal by default: thin bars of fixed thickness regardless of the number of
    categories, and labels that never collide.
    """
    text = [f"{v:.1%}" if percent else f"{v:,.0f}" for v in values]
    marker_color = colors or PALETTE[mode]["series"][0]
    trace = go.Bar(
        x=values if horizontal else [str(c) for c in categories],
        y=[str(c) for c in categories] if horizontal else values,
        orientation="h" if horizontal else "v",
        marker_color=marker_color,
        text=text,
        textposition="outside",
        cliponaxis=False,
        hovertext=hover_text or text,
        hoverinfo="text",
    )
    fig = go.Figure(trace)
    if horizontal:
        fig.update_yaxes(autorange="reversed")
        _layout(fig, mode, height=40 + 34 * len(categories))
        fig.update_layout(bargap=0.35)
        # Room on the right for the value label outside the longest bar.
        top = max((v for v in values if v == v), default=0)
        fig.update_xaxes(tickformat=".1%" if percent else ",", gridcolor=PALETTE[mode]["grid"],
                         range=[0, top * 1.15 if top else 1])
        fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
        return fig
    return _layout(fig, mode, percent_axis=percent)


def trend(df, period_labels, value_column: str, colors: dict[str, str], mode: str,
          percent: bool = False, unit: str = "") -> go.Figure:
    """One line per production line over time."""
    fig = go.Figure()
    for line, color in colors.items():
        rows = df[df["line"] == line]
        if rows.empty:
            continue
        values = rows[value_column]
        shown = [f"{v:.1%}" if percent else f"{v:,.1f}{unit}" for v in values]
        fig.add_trace(
            go.Scatter(
                x=[period_labels[p] for p in rows["period"]],
                y=values,
                name=line,
                mode="lines+markers",
                line=dict(color=color, width=2),
                marker=dict(size=8, color=color),
                hovertemplate=f"{line} · %{{x}}: %{{customdata}}<extra></extra>",
                customdata=shown,
            )
        )
    fig.update_layout(hovermode="x unified")
    return _layout(fig, mode, percent_axis=percent)


def heatmap(pivot, row_labels, column_labels, mode: str) -> go.Figure:
    """Scrap rate by shift (rows) × week (columns). Empty cells: the shift did not run."""
    values = pivot.values
    text = [[("" if v != v else f"{v:.1%}") for v in row] for row in values]  # v != v → NaN
    fig = go.Figure(
        go.Heatmap(
            z=values,
            x=column_labels,
            y=row_labels,
            colorscale=[[i / (len(SEQUENTIAL_BLUE) - 1), c] for i, c in enumerate(SEQUENTIAL_BLUE)],
            text=text,
            texttemplate="%{text}",
            hovertemplate="%{y} · %{x}: %{text}<extra></extra>",
            xgap=2,
            ygap=2,
            colorbar=dict(tickformat=".1%", thickness=10, title=dict(text="Scrap")),
        )
    )
    fig.update_yaxes(autorange="reversed")
    return _layout(fig, mode, height=80 + 60 * len(row_labels))
