"""Component 8: Policy impact view (compare metrics before and after major policy changes)."""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import utils as u

st.set_page_config(page_title="Policy Impact", layout="wide")
st.title("Policy impact: before vs after")
st.write("Pick a policy change and compare each program's average monthly level in the months before it took "
         "effect with the months after. Only zip codes with data in both windows are counted, so changes in "
         "reporting coverage don't distort the comparison.")

f = u.sidebar_filters(period=False, regime=False)
events = u.load_events()
panel = u.apply_filters(u.load_panel(), f)

choices = (events.sort_values("Start").drop_duplicates(["policy", "start_month"])
           .assign(key=lambda e: e["start_month"] + " · " + e["policy"]))
default = choices.index[choices["policy"].eq("Emergency Allotments end")][0]
c1, c2 = st.columns([3, 1])
key = c1.selectbox("Policy change", choices["key"], index=list(choices.index).index(default))
window = c2.slider("Months before / after", 1, 6, 3)
ev = choices[choices["key"] == key].iloc[0]
start = ev["Start"]
before = [(start - pd.DateOffset(months=k)).strftime("%Y-%m") for k in range(window, 0, -1)]
after = [(start + pd.DateOffset(months=k)).strftime("%Y-%m") for k in range(window)]

affected = events[(events["policy"] == ev["policy"]) & (events["start_month"] == ev["start_month"])]
st.caption(f"**{ev['policy']}** took effect {u.month_label(ev['start_month'])}. "
           + " ".join(f"Expected effect on {r.program}: {r.expected_direction} ({r.rationale})."
                      for r in affected.itertuples()))
st.caption(f"Before: {u.month_label(before[0])} – {u.month_label(before[-1])} · "
           f"After: {u.month_label(after[0])} – {u.month_label(after[-1])}")

# ---------------------------------------------------------------- per program comparison
results, zip_rows = [], []
for p in f["programs"]:
    col = u.PROGRAMS[p]["col"]
    b = panel[panel["Month"].isin(before)].groupby("Zip")[col].mean()
    a = panel[panel["Month"].isin(after)].groupby("Zip")[col].mean()
    both = pd.concat([b.rename("Before"), a.rename("After")], axis=1).dropna()
    both = both[both["Before"] > 0]
    if both.empty:
        results.append({"Program": p, "Zip codes": 0})
        continue
    results.append({"Program": p, "Zip codes": len(both), "Before": both["Before"].sum(), "After": both["After"].sum(),
                    "Change %": 100 * (both["After"].sum() / both["Before"].sum() - 1),
                    "Zips up": int((both["After"] > both["Before"]).sum())})
    zip_rows.append(both.assign(Program=p, **{"Change %": 100 * (both["After"] / both["Before"] - 1)}).reset_index())
res = pd.DataFrame(results)

cols = st.columns(len(f["programs"]))
for c, r in zip(cols, res.to_dict("records")):
    unit = u.PROGRAMS[r["Program"]]["unit"]
    if r["Zip codes"] == 0:
        c.metric(r["Program"], "No data", help="This program has no zip-level data in one or both windows.")
        continue
    c.metric(f"{r['Program']}: monthly average after", u.fmt_value(r["After"], unit),
             f"{r['Change %']:+.1f}% vs before", delta_color="off")
    c.caption(f"Before: {u.fmt_value(r['Before'], unit)} · {r['Zips up']} of {r['Zip codes']} zips rose")

ok = res.dropna(subset=["Change %"]) if "Change %" in res else res.iloc[0:0]
if len(ok):
    st.info("**Takeaway:** " + "; ".join(
        f"{r['Program']} {'rose' if r['Change %'] > 0 else 'fell'} {abs(r['Change %']):.1f}%" for r in ok.to_dict("records"))
        + f" in the {window} months after {ev['policy']} compared with the {window} months before. "
          "This is a before/after comparison, so seasonal patterns and other changes in the same months can also "
          "contribute.")
if "LIHEAP" in f["programs"]:
    st.caption("LIHEAP zip-level data covers January–July 2023 only, so it appears only for changes in that window.")

# ---------------------------------------------------------------- monthly charts around the event
st.subheader("Month by month around the change")
st.caption("Each chart uses the same zip codes as the numbers above (those with data both before and after). Dashed "
           "lines show the before and after averages that the percentage compares.")
span = [(start - pd.DateOffset(months=window + 3)).strftime("%Y-%m"),
        (start + pd.DateOffset(months=window + 2)).strftime("%Y-%m")]
x_end = pd.to_datetime(after[-1]) + pd.offsets.MonthEnd(0)
TICK = {"$": dict(tickprefix="$", tickformat="~s"), "lb": dict(tickformat="~s", ticksuffix=" lb"), "households": {}}
ok_programs = [r["Program"] for r in res.to_dict("records") if r["Zip codes"] > 0]
chart_cols = st.columns(max(1, len(ok_programs)))
notes = []
for c, p in zip(chart_cols, ok_programs):
    col, unit, color = u.PROGRAMS[p]["col"], u.PROGRAMS[p]["unit"], u.PROGRAMS[p]["color"]
    zips_used = [zr_["Zip"] for zr_ in zip_rows if zr_["Program"].iloc[0] == p][0]
    sub = panel[panel["Zip"].isin(zips_used) & (panel["Month"] >= span[0]) & (panel["Month"] <= span[1])]
    m = sub.groupby("Month")[col].sum(min_count=1).dropna()
    r = res[res["Program"] == p].iloc[0]
    fig = go.Figure()
    fig.add_vrect(x0=pd.to_datetime(before[0]) - pd.Timedelta(days=15), x1=start - pd.Timedelta(days=15),
                  fillcolor="#a0aec0", opacity=0.12, line_width=0, annotation_text="Before",
                  annotation_position="top left")
    fig.add_vrect(x0=start - pd.Timedelta(days=15), x1=x_end - pd.Timedelta(days=15), fillcolor="#f6ad55",
                  opacity=0.12, line_width=0, annotation_text="After", annotation_position="top left")
    fig.add_trace(go.Scatter(x=pd.to_datetime(m.index), y=m, mode="lines+markers", line=dict(color=color, width=2.5),
                             hovertemplate="<b>%{x|%B %Y}</b><br>%{y:,.0f}<extra></extra>"))
    for months_, val, label in ((before, r["Before"], "before avg"), (after, r["After"], "after avg")):
        fig.add_trace(go.Scatter(x=[pd.to_datetime(months_[0]) - pd.Timedelta(days=12),
                                    pd.to_datetime(months_[-1]) + pd.Timedelta(days=12)], y=[val, val], mode="lines",
                                 line=dict(color="#2d3748", dash="dash", width=2), hoverinfo="skip"))
    fig.add_annotation(x=pd.to_datetime(after[-1]), y=r["After"], text=f"<b>{r['Change %']:+.1f}%</b>",
                       showarrow=False, yshift=14, font=dict(size=13, color="#2d3748"))
    u.style_fig(fig, height=330)
    fig.update_layout(title=dict(text=f"<b>{p}</b>", x=0, font=dict(size=15)), showlegend=False)
    n_months = 2 * window + 5
    fig.update_xaxes(dtick="M2" if n_months <= 12 else "M3", tickformat="%b<br>%Y", tickangle=0, title=None)
    fig.update_yaxes(title=u.PROGRAMS[p]["label"], **TICK.get(unit, {}))
    c.plotly_chart(fig, width="stretch")
    a_vals = m[m.index.isin(after)]
    if len(a_vals) >= 2 and r["Change %"] > 0 and a_vals.iloc[-1] < a_vals.iloc[0]:
        notes.append(f"{p} averaged higher after the change, but it peaked in {u.month_label(a_vals.idxmax())} and "
                     f"was falling by {u.month_label(a_vals.index[-1])}")
    elif len(a_vals) >= 2 and r["Change %"] < 0 and a_vals.iloc[-1] > a_vals.iloc[0]:
        notes.append(f"{p} averaged lower after the change, but it was recovering by {u.month_label(a_vals.index[-1])}")
if notes:
    st.warning("**Read with care:** " + "; ".join(notes) + ". The percentage compares averages, so it can hide a "
               "trend within the window. Try a shorter or longer window with the slider above.")

# ---------------------------------------------------------------- zip distribution
if zip_rows:
    zr = pd.concat(zip_rows)
    zr["City"] = zr["Zip"].map(u.load_cities())
    st.subheader("How the change varied across zip codes")
    progs = list(zr["Program"].unique())
    prog = st.selectbox("Program", progs, index=progs.index("CalFresh") if "CalFresh" in progs else 0)
    zp = zr[zr["Program"] == prog].copy()
    clip = zp["Change %"].clip(-100, 200)
    fig2 = px.histogram(zp.assign(**{"Change % (capped)": clip}), x="Change % (capped)", nbins=30,
                        color_discrete_sequence=[u.PROGRAMS[prog]["color"]],
                        labels={"Change % (capped)": "Change after vs before (%)"})
    fig2.add_vline(x=0, line_color="#222")
    fig2.update_layout(height=320, yaxis_title="Zip codes", margin=dict(t=10))
    st.plotly_chart(fig2, width="stretch")
    st.caption(f"Median zip change: {zp['Change %'].median():+.1f}%. Values beyond −100% to +200% are grouped at the edges.")
    unit = u.PROGRAMS[prog]["unit"]
    show = zp.sort_values("Change %")[["Zip", "City", "Before", "After", "Change %"]].round({"Before": 0, "After": 0})
    show = show.rename(columns={"Before": f"Before, monthly avg ({unit})", "After": f"After, monthly avg ({unit})"})
    st.dataframe(show, hide_index=True, width="stretch", column_config={
        f"Before, monthly avg ({unit})": st.column_config.NumberColumn(format="localized"),
        f"After, monthly avg ({unit})": st.column_config.NumberColumn(format="localized"),
        "Change %": st.column_config.NumberColumn(format="%+.1f%%")})
    u.download(zr, f"policy_impact_{ev['start_month']}")
