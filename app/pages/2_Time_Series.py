"""Component 2: Time series of LIHEAP and food assistance trends."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import utils as u

st.set_page_config(page_title="Time Series", layout="wide")
st.title("Trends over time")
st.write("Monthly totals for each program. Each program has its own chart because they use different units "
         "(households, dollars, pounds). Hover over a point for the exact value.")

f = u.sidebar_filters()
panel = u.apply_filters(u.load_panel(), f)
events = u.load_events()

c1, c2 = st.columns(2)
measure = c1.radio("Show", ["Total", "Per 1,000 households"], horizontal=True,
                   help="Per 1,000 households adjusts for zip code size.")
show_policy = c2.checkbox("Show policy changes", value=True,
                          help="Dotted red lines mark when a policy for that program took effect.")

monthly = panel.groupby("Month")[["LIHEAP", "CalFresh", "FoodBank", "Total_Households"]].sum(min_count=1).reset_index()
counts = panel.groupby("Month")[["LIHEAP", "CalFresh", "FoodBank"]].count().add_suffix("_zips").reset_index()
monthly = monthly.merge(counts, on="Month")
monthly["Date"] = pd.to_datetime(monthly["Month"])

programs = f["programs"]
period_start, period_end = pd.to_datetime(f["period"][0]), pd.to_datetime(f["period"][1]) + pd.offsets.MonthEnd(0)
TICK = {"$": dict(tickprefix="$", tickformat="~s"), "lb": dict(tickformat="~s", ticksuffix=" lb"),
        "households": dict(tickformat=",")}

for p in programs:
    col, unit, color = u.PROGRAMS[p]["col"], u.PROGRAMS[p]["unit"], u.PROGRAMS[p]["color"]
    s = monthly[col]
    if measure != "Total":
        # households only for zips that reported this program that month
        hh = panel.dropna(subset=[col]).groupby("Month")["Total_Households"].sum()
        s = 1000 * monthly[col] / monthly["Month"].map(hh)
    title = u.PROGRAMS[p]["label"] + ("" if measure == "Total" else " per 1,000 households")
    fig = go.Figure(go.Scatter(
        x=monthly["Date"], y=s, mode="lines+markers", line=dict(color=color, width=2.5), marker=dict(size=5),
        name=p,
        customdata=monthly[[f"{col}_zips"]],
        hovertemplate="<b>%{x|%B %Y}</b><br>%{y:,.0f}<br>%{customdata[0]} zip codes reporting<extra></extra>"))
    if show_policy:
        u.add_policy_lines(fig, events, [p], f["period"][0], f["period"][1])
    u.style_fig(fig, height=320)
    fig.update_layout(title=dict(text=f"<b>{title}</b>", x=0, font=dict(size=16)), showlegend=False)
    fig.update_xaxes(title="Month", range=[period_start - pd.Timedelta(days=15), period_end],
                     dtick="M6" if (period_end - period_start).days > 900 else "M3", tickformat="%b %Y")
    fig.update_yaxes(title=None, rangemode="tozero" if s.min(skipna=True) >= 0 else "normal",
                     **(TICK.get(unit, {}) if measure == "Total" else {}))
    if s.notna().sum() == 0:
        fig.add_annotation(text="No data in the selected period", x=0.5, y=0.5, xref="paper", yref="paper",
                           showarrow=False, font=dict(size=14, color="#718096"))
    st.plotly_chart(fig, width="stretch")

if "LIHEAP" in programs:
    st.caption("LIHEAP zip-level data is available for January–July 2023 only, so its panel is blank outside "
               "those months.")
if show_policy:
    shown = events[events["program"].isin(programs)]
    shown = shown[(shown["start_month"] >= f["period"][0]) & (shown["start_month"] <= f["period"][1])]
    if len(shown):
        with st.expander(f"Policy changes marked on the chart ({len(shown)})"):
            st.dataframe(shown[["start_month", "program", "policy", "expected_direction", "rationale"]]
                         .rename(columns={"start_month": "Effective", "program": "Program", "policy": "Policy",
                                          "expected_direction": "Expected effect", "rationale": "Why"}),
                         hide_index=True, width="stretch")

# ---------------------------------------------------------------- summary
st.subheader("Change over the selected period")
cols = st.columns(len(programs))
for c, p in zip(cols, programs):
    col = u.PROGRAMS[p]["col"]
    s = monthly.dropna(subset=[col])
    s = s[s[f"{col}_zips"] > 0]
    if len(s) < 2:
        c.metric(p, "No data in period")
        continue
    first, last = s.iloc[0], s.iloc[-1]
    pct = 100 * (last[col] - first[col]) / first[col]
    c.metric(f"{p}: {u.month_label(last['Month'])}", u.fmt_value(last[col], u.PROGRAMS[p]["unit"]),
             f"{pct:+.1f}% since {u.month_label(first['Month'])}")
st.caption(u.filter_summary(f))

out = monthly[["Month"] + [u.PROGRAMS[p]["col"] for p in programs] + [f"{u.PROGRAMS[p]['col']}_zips" for p in programs]]
u.download(out, "time_series_monthly_totals")
