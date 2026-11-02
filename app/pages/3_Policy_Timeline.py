"""Component 3: Policy timeline overlay showing major changes and effective dates."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import utils as u

st.set_page_config(page_title="Policy Timeline", layout="wide")
st.title("Policy timeline")
st.write("Major federal and state policy changes affecting LIHEAP, CalFresh and food banks, with the months each "
         "took effect. The chart below lays the same dates over the program's monthly totals.")

f = u.sidebar_filters(zips=True, regime=False, default_period=("2019-01", "2025-08"))
events = u.load_events()
lo, hi = pd.to_datetime(f["period"][0]), pd.to_datetime(f["period"][1]) + pd.offsets.MonthEnd(0)
ev = events[events["program"].isin(f["programs"]) & (events["End"] >= lo) & (events["Start"] <= hi)].copy()

DIRECTION = {"increase": ("Expected to raise", "#2f855a"), "decrease": ("Expected to lower", "#c53030"),
             "uncertain": ("Effect unclear", "#a0aec0")}


def wrap(text, width=38):
    words, lines, line = text.split(), [], ""
    for w in words:
        if len(line) + len(w) + 1 > width and line:
            lines.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    return "<br>".join(lines + [line])


def span_label(e):
    a, b = u.month_label(e["start_month"]), u.month_label(e["end_month"])
    return a if a == b else f"{a} – {b}"


# ---------------------------------------------------------------- timeline, one tab per program
st.subheader("When each policy was in effect")
st.caption("Each bar runs from the month a policy took effect to the end of its phase-in. Colour shows which way it "
           "was expected to push that program. Hover over a bar for the reasoning.")
if ev.empty:
    st.info("No policy changes for these programs in the selected period.")
else:
    tabs = st.tabs([f"{p} ({(ev['program'] == p).sum()})" for p in f["programs"]])
    for tab, p in zip(tabs, f["programs"]):
        with tab:
            sub = ev[ev["program"] == p].sort_values("Start")
            if sub.empty:
                st.info(f"No {p} policy changes in the selected period.")
                continue
            sub = sub.assign(Row=sub["policy"].map(wrap), When=sub.apply(span_label, axis=1))
            fig = go.Figure()
            for direction, (name, color) in DIRECTION.items():
                d = sub[sub["expected_direction"] == direction]
                if d.empty:
                    continue
                fig.add_trace(go.Bar(
                    y=d["Row"], base=d["Start"], x=(d["End"] - d["Start"]).dt.total_seconds() * 1000,
                    orientation="h", marker=dict(color=color), name=name, width=0.55,
                    customdata=d[["When", "rationale"]],
                    hovertemplate="<b>%{y}</b><br>%{customdata[0]}<br>%{customdata[1]}<extra></extra>"))
                # a marker at the start so one-month changes are still easy to see
                fig.add_trace(go.Scatter(y=d["Row"], x=d["Start"], mode="markers", showlegend=False,
                                         marker=dict(symbol="diamond", size=11, color=color,
                                                     line=dict(color="white", width=1)),
                                         customdata=d[["When", "rationale"]],
                                         hovertemplate="<b>%{y}</b><br>%{customdata[0]}<br>%{customdata[1]}<extra></extra>"))
            u.style_fig(fig, height=90 + 52 * len(sub))
            fig.update_layout(barmode="overlay", bargap=0.4)
            fig.update_xaxes(type="date", range=[lo - pd.Timedelta(days=20), hi], dtick="M12", tickformat="%Y",
                             showgrid=True, gridcolor="#edf2f7", title=None)
            fig.update_yaxes(categoryorder="array", categoryarray=list(sub["Row"])[::-1], title=None,
                             tickfont=dict(size=13), showgrid=False)
            st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------- overlay
st.subheader("Policy changes over program totals")
c1, c2 = st.columns([1, 2])
prog = c1.selectbox("Program to plot", f["programs"],
                    index=f["programs"].index("CalFresh") if "CalFresh" in f["programs"] else 0)
col = u.PROGRAMS[prog]["col"]
pe = ev[ev["program"] == prog].sort_values("Start").reset_index(drop=True)
pe["No."] = range(1, len(pe) + 1)
highlight = c2.selectbox("Highlight a policy", ["None"] + [f"{r['No.']}. {r['policy']}" for _, r in pe.iterrows()],
                         index=0)

panel = u.apply_filters(u.load_panel(), f)
monthly = panel.groupby("Month")[col].sum(min_count=1).dropna().reset_index()
monthly["Date"] = pd.to_datetime(monthly["Month"])
unit = u.PROGRAMS[prog]["unit"]
fig2 = go.Figure(go.Scatter(x=monthly["Date"], y=monthly[col], mode="lines+markers", marker_size=5,
                            line=dict(color=u.PROGRAMS[prog]["color"], width=2.5), name=prog,
                            hovertemplate="<b>%{x|%B %Y}</b><br>%{y:,.0f}<extra></extra>"))
pe["Shown at"] = pe["Start"].clip(lower=lo)  # changes that began before the period are marked at its start
for when, grp in pe.groupby("Shown at"):
    hl = grp[grp.apply(lambda r: highlight.startswith(f"{r['No.']}. "), axis=1)]
    for _, e in hl.iterrows():
        fig2.add_vrect(x0=max(e["Start"], lo), x1=min(e["End"], hi), fillcolor=DIRECTION[e["expected_direction"]][1],
                       opacity=0.15, line_width=0)
    color = DIRECTION[grp.iloc[0]["expected_direction"]][1] if grp["expected_direction"].nunique() == 1 else "#4a5568"
    fig2.add_vline(x=when.timestamp() * 1000, line_dash="dot", line_width=2 if len(hl) else 1,
                   line_color=color if len(hl) else "#a0aec0")
    # policies starting in the same month share one badge, e.g. "3 · 4"
    fig2.add_annotation(x=when, y=1.02, yref="paper", text="<b>" + " · ".join(map(str, grp["No."])) + "</b>",
                        showarrow=False, yanchor="bottom", font=dict(size=12, color="white"), bgcolor=color,
                        borderpad=3)
u.style_fig(fig2, height=420)
fig2.update_layout(margin=dict(t=50), showlegend=False)
fig2.update_xaxes(type="date", range=[lo - pd.Timedelta(days=20), hi], dtick="M12" if (hi - lo).days > 1100 else "M3",
                  tickformat="%Y" if (hi - lo).days > 1100 else "%b %Y", title="Month")
fig2.update_yaxes(title=u.PROGRAMS[prog]["label"], rangemode="tozero",
                  **({"tickprefix": "$", "tickformat": "~s"} if unit == "$" else {"tickformat": "~s"}))
st.plotly_chart(fig2, width="stretch")
if prog == "LIHEAP":
    st.caption("LIHEAP zip-level totals exist only for January–July 2023.")
if len(pe):
    key = pe.assign(When=pe.apply(span_label, axis=1),
                    Effect=pe["expected_direction"].map(lambda d: DIRECTION[d][0]))[["No.", "policy", "When", "Effect"]]
    st.dataframe(key.rename(columns={"policy": "Policy", "When": "In effect"}), hide_index=True, width="stretch")
    st.caption("Numbered badges on the chart match this list. Pick one under “Highlight a policy” to shade its window. "
               + u.filter_summary(f))

# ---------------------------------------------------------------- table
st.subheader("Policy details")
table = ev[["start_month", "end_month", "program", "policy", "change_type", "expected_direction", "rationale"]] \
    .sort_values("start_month").rename(columns={
        "start_month": "Effective", "end_month": "Phase-in ends", "program": "Program", "policy": "Policy",
        "change_type": "Type", "expected_direction": "Expected effect", "rationale": "Why"})
st.dataframe(table, hide_index=True, width="stretch")
u.download(table, "policy_timeline")
