"""Component 4: Correlation explorer (lag periods, metric selection, policy regime filter)."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import utils as u

st.set_page_config(page_title="Correlation Explorer", layout="wide")
st.title("Correlation explorer")
st.write("Do zip codes with more LIHEAP enrollment also receive more food assistance? Pick an outcome and a time "
         "lag (how many months earlier LIHEAP enrollment is measured).")

f = u.sidebar_filters(program=False, period=False)
lags = u.apply_filters(u.load_lags(), f)
st.caption("Uses February–October 2023, the months with zip-level LIHEAP data at lags of 0–3 months. "
           "Policy regimes here: Emergency Allotments active (Feb–Mar), ended (Apr–Jun), work rules resumed (Jul–Oct).")

c1, c2, c3, c4 = st.columns(4)
outcome = c1.selectbox("Outcome", ["CalFresh", "Food bank"])
lag = c2.select_slider("LIHEAP lag (months earlier)", options=[0, 1, 2, 3], value=1,
                       help="1 = LIHEAP enrollment one month before the outcome month.")
per_hh = c3.radio("Measure", ["Totals", "Per household"], horizontal=True,
                  help="Per household divides both values by the zip's household count, removing zip-size effects.")
method = c4.radio("Method", ["Spearman", "Pearson"], horizontal=True,
                  help="Spearman (rank-based) is less affected by a few very large zip codes.")

ycol = u.PROGRAMS[outcome]["col"]
d = lags.copy()
x, y = d[f"LIHEAP_lag{lag}"], d[ycol]
if per_hh == "Per household":
    x, y = 1000 * x / d["Total_Households"], y / d["Total_Households"]
d = d.assign(x=x, y=y).dropna(subset=["x", "y"])
d["Regime"] = d["Month"].map(u.regime_of)
res = u.correlation(d["x"], d["y"], method.lower())

if res["n"] < 5:
    st.warning("Too few zip-months for these filters. Clear the zip or regime filter.")
    st.stop()

# ---------------------------------------------------------------- headline
k1, k2, k3 = st.columns(3)
k1.metric(f"{method} correlation", f"{res['r']:.2f}", help="−1 to 1. 0 = no relationship, 1 = perfect.")
k2.metric("95% confidence interval", f"{res['lo']:.2f} to {res['hi']:.2f}")
k3.metric("Zip-months", f"{res['n']:,}")
sig = "statistically significant (p < 0.05)" if res["p"] < 0.05 else "not statistically significant"
st.info(f"**Takeaway:** at a {lag}-month lag, LIHEAP enrollment has a **{u.strength(res['r'])}** "
        f"{'positive' if res['r'] > 0 else 'negative'} relationship with {outcome} "
        f"({method} {res['r']:.2f}), {sig}. Correlation shows where the programs overlap, not that one causes the other.")

left, right = st.columns(2)
with left:
    st.subheader("Each zip code")
    # One dot per zip: averages over the months in view, which is easier to read than every zip-month
    zp = d.groupby("Zip").agg(x=("x", "mean"), y=("y", "mean"), months=("Month", "nunique")).reset_index()
    zp = zp[(zp["x"] > 0) & (zp["y"] > 0)]
    zp["Zip code"] = zp["Zip"].map(u.zip_label)
    unit_y = u.PROGRAMS[outcome]["unit"]
    if per_hh == "Per household":
        xl = "LIHEAP enrollees per 1,000 households"
        yl = ("CalFresh $ per household" if outcome == "CalFresh" else "Food bank lb per household") + " (monthly avg)"
    else:
        xl = f"LIHEAP enrollment, {lag} month{'s' if lag != 1 else ''} earlier (monthly avg)"
        yl = u.PROGRAMS[outcome]["label"] + " (monthly avg)"
    fig = go.Figure(go.Scatter(
        x=zp["x"], y=zp["y"], mode="markers", text=zp["Zip code"], customdata=zp[["months"]],
        marker=dict(size=9, color=u.PROGRAMS[outcome]["color"], opacity=0.7, line=dict(color="white", width=1)),
        hovertemplate="<b>%{text}</b><br>LIHEAP: %{x:,.1f}<br>" + outcome + ": %{y:,.1f}"
                      "<br>%{customdata[0]} months<extra></extra>"))
    # trend line fitted on the log scale (straight line on these axes)
    if len(zp) >= 5:
        b, a = np.polyfit(np.log10(zp["x"]), np.log10(zp["y"]), 1)
        xs = np.logspace(np.log10(zp["x"].min()), np.log10(zp["x"].max()), 50)
        fig.add_trace(go.Scatter(x=xs, y=10 ** (a + b * np.log10(xs)), mode="lines", hoverinfo="skip",
                                 line=dict(color="#2d3748", dash="dash", width=2)))
    u.style_fig(fig, height=430)
    fig.update_layout(showlegend=False)
    fig.update_xaxes(title=xl, **u.log_ticks(zp["x"]))
    fig.update_yaxes(title=yl, **u.log_ticks(zp["y"], "" if per_hh == "Per household" else unit_y))
    st.plotly_chart(fig, width="stretch")
    st.caption(f"Each dot is one zip code ({len(zp)} shown), averaged over the months in view. Dots rising to the "
               "right mean zip codes with more LIHEAP enrollment also receive more assistance; the dashed line shows "
               "the overall trend. Axes use a log scale (equal spacing for 1→10→100) so small and large zip codes both fit.")

with right:
    st.subheader("Which lag is strongest?")
    rows = []
    for L in range(4):
        xx, yy = lags[f"LIHEAP_lag{L}"], lags[ycol]
        if per_hh == "Per household":
            xx, yy = 1000 * xx / lags["Total_Households"], yy / lags["Total_Households"]
        r = u.correlation(xx, yy, method.lower())
        rows.append({"Lag (months)": L, **r})
    prof = pd.DataFrame(rows)
    fig2 = go.Figure(go.Scatter(x=prof["Lag (months)"], y=prof["r"], mode="lines+markers",
                                error_y=dict(type="data", symmetric=False, array=prof["hi"] - prof["r"],
                                             arrayminus=prof["r"] - prof["lo"]),
                                line_color=u.PROGRAMS[outcome]["color"]))
    fig2.add_vline(x=lag, line_dash="dot", line_color="#b42318")
    fig2.update_layout(height=430, xaxis=dict(tickvals=[0, 1, 2, 3], title="LIHEAP lag (months)"),
                       yaxis=dict(title=f"{method} correlation", range=[min(0, prof['lo'].min() - 0.05), 1]),
                       margin=dict(t=10))
    st.plotly_chart(fig2, width="stretch")
    st.caption("Error bars are 95% confidence intervals. Overlapping bars mean no lag is clearly better.")

# ---------------------------------------------------------------- by regime
st.subheader("Does the relationship change across policy regimes?")
reg_rows = []
for name, g in d.groupby("Regime"):
    r = u.correlation(g["x"], g["y"], method.lower())
    reg_rows.append({"Policy regime": name, "Correlation": r["r"], "95% CI low": r["lo"], "95% CI high": r["hi"],
                     "Zip-months": r["n"]})
reg = pd.DataFrame(reg_rows)
st.dataframe(reg, hide_index=True, width="stretch",
             column_config={c: st.column_config.NumberColumn(format="%.2f") for c in
                            ["Correlation", "95% CI low", "95% CI high"]})
st.caption("If the confidence intervals overlap, the regimes are not reliably different.")

# ---------------------------------------------------------------- zip ranking
with st.expander("Zip codes where LIHEAP and assistance move together most (from the correlation report)"):
    rank = pd.read_csv(u.DATA / "Modeling" / "Zip_Correlation_Ranking.csv", dtype={"Zip Code": str})
    if f["zips"]:
        rank = rank[rank["Zip Code"].isin(f["zips"])]
    st.dataframe(rank, hide_index=True, width="stretch")
    st.caption("Each zip has only 5–6 months, so individual zip correlations are noisy; treat this as a list for "
               "closer review.")

u.download(d[["Zip", "City", "Month", "Regime", f"LIHEAP_lag{lag}", ycol, "Total_Households", "x", "y"]]
           .rename(columns={"x": "x_plotted", "y": "y_plotted"}), f"correlation_{outcome}_lag{lag}")
