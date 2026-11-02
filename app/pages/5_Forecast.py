"""Component 5: Predictive model view (forecast food assistance from LIHEAP inputs)."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import utils as u
from scenario import load_bundle, load_features, predict

st.set_page_config(page_title="Forecast", layout="wide")
st.title("Forecast: predicting food assistance from LIHEAP and recent history")
st.write("The model predicts each zip code's CalFresh benefits or food bank pounds for a month using LIHEAP "
         "enrollment over the previous three months, last month's assistance, and census demographics.")

TEST_RESULTS = {  # held-out July-August 2023, from the Predictive Model Evaluation Report
    "CalFresh_Dollars": {"model": 7.2, "naive": 3.4},
    "FoodBank_Pounds": {"model": 20.8, "naive": 20.5},
}
TARGETS = {"CalFresh": "CalFresh_Dollars", "Food bank": "FoodBank_Pounds"}


@st.cache_resource(show_spinner="Loading models (the first run trains them, about a minute)...")
def get_bundle():
    return load_bundle()


@st.cache_data
def get_feats():
    return load_features()


bundle, feats = get_bundle(), get_feats()
f = u.sidebar_filters(program=False, period=False, regime=False)

c1, c2 = st.columns(2)
prog = c1.radio("Program", list(TARGETS), horizontal=True)
target = TARGETS[prog]
entry = bundle[target]
unit = u.PROGRAMS[prog]["unit"]
month = c2.selectbox("Month", entry["months"], index=len(entry["months"]) - 1, format_func=u.month_label)

# ---------------------------------------------------------------- predictions for every month
rows = feats[feats["LIHEAP_lag1_observed"] == 1].dropna(subset=entry["features"] + [target]).copy()
if f["zips"]:
    rows = rows[rows["Zip Code"].isin(f["zips"])]
if rows.empty:
    st.warning("No zip codes with model inputs for the selected zips. Clear the zip filter.")
    st.stop()
pred = predict(entry, rows)
rows = rows.assign(Predicted=pred["pred"], Low=pred["lower"], High=pred["upper"])

monthly = rows.groupby("Month_Year")[[target, "Predicted"]].sum().reset_index()
monthly["Date"] = pd.to_datetime(monthly["Month_Year"])
this = rows[rows["Month_Year"] == month].copy()
this["Error %"] = 100 * (this["Predicted"] - this[target]) / this[target]

k1, k2, k3, k4 = st.columns(4)
k1.metric(f"Actual total, {u.month_label(month)}", u.fmt_value(this[target].sum(), unit))
k2.metric("Model prediction", u.fmt_value(this["Predicted"].sum(), unit),
          f"{100 * (this['Predicted'].sum() / this[target].sum() - 1):+.1f}% vs actual", delta_color="off")
k3.metric("Typical zip error (held-out test)", f"{TEST_RESULTS[target]['model']:.1f}%",
          help="Average % error per zip on July–August 2023, months the model never saw during evaluation.")
k4.metric("“Same as last month” error", f"{TEST_RESULTS[target]['naive']:.1f}%",
          help="A simple benchmark: predict each zip's value as last month's value.")
st.info(f"**How good is it?** On months it had not seen, the {entry['model_name']} model was off by about "
        f"{TEST_RESULTS[target]['model']:.0f}% per zip code, compared with {TEST_RESULTS[target]['naive']:.0f}% for "
        "simply repeating last month's value. Last month's value carries most of the prediction; LIHEAP enrollment adds "
        "a little for CalFresh and almost nothing for food bank. Use these forecasts as a cross-check, not a replacement "
        "for recent actuals.")

left, right = st.columns(2)
with left:
    st.subheader("County total: actual vs predicted")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=monthly["Date"], y=monthly[target], name="Actual", mode="lines+markers",
                             line_color="#222"))
    fig.add_trace(go.Scatter(x=monthly["Date"], y=monthly["Predicted"], name="Model", mode="lines+markers",
                             line=dict(color=u.PROGRAMS[prog]["color"], dash="dash")))
    fig.add_vline(x=pd.Timestamp("2023-04-01").timestamp() * 1000, line_dash="dot", line_color="#b42318",
                  annotation_text="Emergency Allotments end", annotation_position="bottom right")
    u.style_fig(fig, height=400)
    fig.update_xaxes(title="Month (2023)", dtick="M1", tickformat="%b", tickangle=0)
    fig.update_layout(legend=dict(y=1.15))
    fig.update_yaxes(title=u.PROGRAMS[prog]["label"], rangemode="tozero",
                     **({"tickprefix": "$", "tickformat": "~s"} if unit == "$" else {"tickformat": "~s"}))
    st.plotly_chart(fig, width="stretch")
    st.caption("The deployed model is fit on all of February–August 2023, so this chart shows fit, not a blind test. "
               "Blind-test accuracy is in the boxes above.")
with right:
    st.subheader(f"Each zip code: actual vs predicted, {u.month_label(month)}")
    this["Zip label"] = this["Zip Code"].map(u.zip_label)
    fig2 = go.Figure(go.Scatter(
        x=this[target], y=this["Predicted"], mode="markers", text=this["Zip label"], customdata=this[["Error %"]],
        error_y=dict(type="data", symmetric=False, array=this["High"] - this["Predicted"],
                     arrayminus=this["Predicted"] - this["Low"], thickness=1, width=0, color="rgba(113,128,150,0.3)"),
        marker=dict(color=u.PROGRAMS[prog]["color"], size=8, line=dict(color="white", width=1)),
        hovertemplate="<b>%{text}</b><br>Actual: %{x:,.0f}<br>Predicted: %{y:,.0f}<br>Error: %{customdata[0]:+.1f}%"
                      "<extra></extra>"))
    lim = [this[[target, "Low"]].min().min() * 0.8, this[[target, "High"]].max().max() * 1.2]
    fig2.add_trace(go.Scatter(x=lim, y=lim, mode="lines", line=dict(color="#4a5568", dash="dot"), hoverinfo="skip"))
    fig2.add_annotation(x=np.log10(lim[0] * 4), y=np.log10(lim[0] * 4), text="perfect prediction",
                        showarrow=False, textangle=-38, yshift=-14, xshift=14, font=dict(size=11, color="#4a5568"))
    u.style_fig(fig2, height=400)
    fig2.update_layout(showlegend=False)
    ticks = u.log_ticks(pd.concat([this[target], this["Low"], this["High"]]), unit)
    fig2.update_xaxes(title=f"Actual {prog} in {u.month_label(month)}", range=np.log10(lim).tolist(), **ticks)
    fig2.update_yaxes(title="Model prediction", range=np.log10(lim).tolist(), **ticks)
    st.plotly_chart(fig2, width="stretch")
    st.caption("Each dot is one zip code: across = what actually happened, up = what the model predicted. Dots on the "
               "dotted line were predicted exactly; above it means the model guessed too high. Grey bars are 90% "
               "ranges. Both axes use a log scale so small and large zip codes fit on one chart.")

# ---------------------------------------------------------------- try your own LIHEAP inputs
st.subheader("What if a zip code had more or fewer LIHEAP enrollees?")
prev = [u.month_label((pd.to_datetime(month) - pd.DateOffset(months=k)).strftime("%Y-%m")) for k in (1, 2, 3)]
st.write(
    f"The model predicts {prog} for **{u.month_label(month)}** partly from how many households were enrolled in "
    f"LIHEAP in the three months before it ({prev[2]}, {prev[1]} and {prev[0]}).")
st.markdown(
    "1. **Choose a zip code.** The three boxes fill in with that zip code's actual LIHEAP enrollment.\n"
    "2. **Change any of the numbers**, for example double them, to imagine more households enrolled.\n"
    f"3. **Compare the two forecasts** below to see how much the model's {u.month_label(month)} prediction moves.")
zips = sorted(this["Zip Code"])
z = st.selectbox("Zip code", zips, format_func=u.zip_label)
base = this[this["Zip Code"] == z].iloc[[0]]
i1, i2, i3 = st.columns(3)
l3 = i1.number_input(f"Households enrolled in {prev[2]}", 0, 2000, int(base["LIHEAP_lag3"].iloc[0]), key=f"l3_{z}_{month}")
l2 = i2.number_input(f"Households enrolled in {prev[1]}", 0, 2000, int(base["LIHEAP_lag2"].iloc[0]), key=f"l2_{z}_{month}")
l1 = i3.number_input(f"Households enrolled in {prev[0]}", 0, 2000, int(base["LIHEAP_lag1"].iloc[0]), key=f"l1_{z}_{month}")

custom = base.copy()
custom["LIHEAP_lag1"], custom["LIHEAP_lag2"], custom["LIHEAP_lag3"] = l1, l2, l3
custom["LIHEAP_lag1_per_1k_HH"] = 1000 * l1 / np.exp(custom["Log_Households"])
custom["LIHEAPxPoverty"] = l1 * (custom["Poverty_Rate"] - feats["Poverty_Rate"].median())
custom["LIHEAPxRent"] = l1 * (custom["Median_Rent_k"] - feats["Median_Rent_k"].median())
p_base, p_new = predict(entry, base).iloc[0], predict(entry, custom).iloc[0]
r1, r2, r3 = st.columns(3)
r1.metric(f"{u.month_label(month)} forecast, actual enrollment", u.fmt_value(p_base["pred"], unit))
r2.metric(f"{u.month_label(month)} forecast, your numbers", u.fmt_value(p_new["pred"], unit),
          f"{100 * (p_new['pred'] / p_base['pred'] - 1):+.2f}%")
r3.metric("90% range for your forecast",
          f"{u.fmt_value(p_new['lower'], unit)} – {u.fmt_value(p_new['upper'], unit)}".replace("$", "\\$"))
st.caption(f"What actually happened in {u.month_label(month)}: {u.fmt_value(base[target].iloc[0], unit)}. "
           "Changes are usually small because last month's value matters far more to the model than LIHEAP. "
           "For county-wide what-if changes, use the Scenario Analysis page.")

# ---------------------------------------------------------------- table + download
st.subheader("Predictions by zip code")
table = this[["Zip Code", "Zip label", target, "Predicted", "Low", "High", "Error %"]].rename(columns={
    "Zip label": "Zip code (city)", target: "Actual", "Low": "90% range low", "High": "90% range high"}) \
    .drop(columns="Zip Code").sort_values("Actual", ascending=False)
money_cols = ["Actual", "Predicted", "90% range low", "90% range high"]
table[money_cols] = table[money_cols].round(0)
table = table.rename(columns={c: f"{c} ({unit})" for c in money_cols})
st.dataframe(table, hide_index=True, width="stretch",
             column_config={**{f"{c} ({unit})": st.column_config.NumberColumn(format="localized") for c in money_cols},
                            "Error %": st.column_config.NumberColumn(format="%+.1f%%")})
u.download(rows[["Zip Code", "Month_Year", target, "Predicted", "Low", "High"]], f"forecast_{target}")
