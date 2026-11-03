"""Component 7: Demographic breakdown view (drill-down by poverty, unemployment and more)."""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import utils as u

st.set_page_config(page_title="Demographics", layout="wide")
st.title("Demographic breakdown")
st.write("Zip codes are split into three equal groups (low, middle, high) by the measure you choose. "
         "Compare how much assistance each group receives per household, then drill into one group.")

f = u.sidebar_filters()
panel = u.apply_filters(u.load_panel(), f)

c1, c2 = st.columns(2)
demo = c1.selectbox("Split zip codes by", list(u.DEMOGRAPHICS), format_func=u.DEMOGRAPHICS.get)
n_groups = c2.radio("Number of groups", [3, 4, 5], horizontal=True, format_func=lambda k: {3: "Thirds", 4: "Quarters", 5: "Fifths"}[k])

# ---------------------------------------------------------------- one row per zip for the period
agg = {demo: "mean", "Total_Households": "mean"}
for p in f["programs"]:
    agg[u.PROGRAMS[p]["col"]] = "mean"
z = panel.groupby("Zip").agg(agg).reset_index()
z["City"] = z["Zip"].map(u.load_cities())
z = z.dropna(subset=[demo, "Total_Households"])
z = z[z["Total_Households"] > 0]
for p in f["programs"]:
    col = u.PROGRAMS[p]["col"]
    scale = 1000 if p == "LIHEAP" else 1  # LIHEAP per 1,000 HH; $ and lb per household
    z[f"{p} per HH"] = scale * z[col] / z["Total_Households"]

if len(z) < n_groups * 3:
    st.warning("Too few zip codes for these filters. Widen the time period or clear the zip filter.")
    st.stop()

names = {3: ["Low", "Middle", "High"], 4: ["Lowest", "Lower-middle", "Upper-middle", "Highest"],
         5: ["Lowest", "Low", "Middle", "High", "Highest"]}[n_groups]
z["Group"], bins = pd.qcut(z[demo].rank(method="first"), n_groups, labels=names, retbins=True)
ranges = z.groupby("Group", observed=True)[demo].agg(["min", "max"])
z["Group label"] = z["Group"].map({g: f"{g} ({ranges.loc[g, 'min']:,.1f}–{ranges.loc[g, 'max']:,.1f})" for g in names})
order = [f"{g} ({ranges.loc[g, 'min']:,.1f}–{ranges.loc[g, 'max']:,.1f})" for g in names]

PER_HH_LABEL = {"LIHEAP": "LIHEAP enrollees per 1,000 households", "CalFresh": "CalFresh $ per household per month",
                "Food bank": "Food bank lb per household per month"}

# ---------------------------------------------------------------- group comparison
st.subheader(f"Assistance per household by {u.DEMOGRAPHICS[demo].lower()} group")
long = z.melt(id_vars=["Zip", "Group label"], value_vars=[f"{p} per HH" for p in f["programs"]],
              var_name="Program", value_name="Value").dropna()
long["Program"] = long["Program"].str.replace(" per HH", "")
summary = long.groupby(["Program", "Group label"], observed=True)["Value"].agg(["median", "count"]).reset_index()
Y_TITLE = {"LIHEAP": "Enrollees per 1,000 households", "CalFresh": "$ per household, per month",
           "Food bank": "Pounds per household, per month"}
VALUE_FMT = {"LIHEAP": "{:.1f}", "CalFresh": "${:,.0f}", "Food bank": "{:.1f} lb"}
cols = st.columns(len(f["programs"]))
for c, p in zip(cols, f["programs"]):
    sp = summary[summary["Program"] == p].set_index("Group label").reindex(order)
    fig = go.Figure(go.Bar(x=[g.split(" (")[0] for g in order], y=sp["median"], marker_color=u.PROGRAMS[p]["color"],
                           text=[VALUE_FMT[p].format(v) if pd.notna(v) else "" for v in sp["median"]],
                           textposition="outside", customdata=sp[["count"]].to_numpy(),
                           hovertext=order,
                           hovertemplate="<b>%{hovertext}</b><br>Typical zip: %{text}<br>%{customdata[0]} zip codes"
                                         "<extra></extra>"))
    u.style_fig(fig, height=340)
    fig.update_layout(title=dict(text=f"<b>{p}</b>", x=0, font=dict(size=15)), showlegend=False)
    fig.update_yaxes(title=Y_TITLE[p], rangemode="tozero", range=[0, sp["median"].max() * 1.2])
    fig.update_xaxes(title=f"{u.DEMOGRAPHICS[demo]} group")
    c.plotly_chart(fig, width="stretch")

example_p = "CalFresh" if "CalFresh" in f["programs"] else f["programs"][0]
ex = summary[(summary["Program"] == example_p) & (summary["Group label"] == order[-1])]["median"]
if len(ex):
    st.caption(
        "**How to read these bars:** each bar is the *typical* (median) zip code in that group, after dividing by the "
        f"number of households so big and small zip codes compare fairly. For example, in the "
        f"{names[-1].lower()} {u.DEMOGRAPHICS[demo].lower()} group the typical zip code received "
        f"{VALUE_FMT[example_p].format(ex.iloc[0]).replace('$', chr(92) + '$')} "
        f"{'per household each month' if example_p != 'LIHEAP' else 'LIHEAP enrollees per 1,000 households'}. "
        "Group ranges are shown in the drill-down below.")

hi, lo = order[-1], order[0]
lines = []
for p in f["programs"]:
    s = summary[summary["Program"] == p].set_index("Group label")["median"]
    if lo in s and hi in s and s[lo] > 0:
        lines.append(f"**{p}:** the {names[-1].lower()} group receives **{s[hi] / s[lo]:.1f}×** the "
                     f"{names[0].lower()} group's level per household")
if lines:
    st.info("**Takeaway:** " + "; ".join(lines) + ". Medians are used so a few very large zip codes don't dominate.")

# ---------------------------------------------------------------- relationship scatter
st.subheader("Every zip code")
prog = st.selectbox("Program for the scatter", f["programs"])
z["Zip label"] = z["Zip"].map(u.zip_label)
fig2 = px.scatter(z, x=demo, y=f"{prog} per HH", color="Group label", category_orders={"Group label": order},
                  hover_name="Zip label", size="Total_Households", size_max=22,
                  labels={demo: u.DEMOGRAPHICS[demo], f"{prog} per HH": PER_HH_LABEL[prog], "Group label": "Group"})
fig2.update_layout(height=420, margin=dict(t=10))
st.plotly_chart(fig2, width="stretch")
r = u.correlation(z[demo], z[f"{prog} per HH"])
if not np.isnan(r["r"]):
    st.caption(f"Bubble size = number of households. Spearman correlation across zip codes: {r['r']:.2f} "
               f"({u.strength(r['r'])}, n = {r['n']}).")

# ---------------------------------------------------------------- drill-down
st.subheader("Drill down into one group")
measure = u.DEMOGRAPHICS[demo]
measure_l = measure.split(" (")[0].lower()
unit_sfx = "%" if "(%)" in measure else ""
fmt_v = (lambda v: f"${v:,.0f}") if demo == "Median_Gross_Rent" else (lambda v: f"{v:,.1f}{unit_sfx}")
size_word = {3: "thirds", 4: "quarters", 5: "fifths"}[n_groups]
st.markdown(
    f"**What the groups mean:** all {len(z)} zip codes with census data are ranked from lowest to highest "
    f"{measure_l} and split into {size_word} with about the same number of zip codes in each. "
    f"**{names[0]}** is the {size_word[:-1]} with the lowest {measure_l} and **{names[-1]}** the {size_word[:-1]} with the highest. "
    "The numbers in brackets are each group's range.")
gt = (z.groupby("Group label", observed=True)
       .agg(zips=("Zip", "count"), lo=(demo, "min"), hi=(demo, "max"), med=(demo, "median"))
       .reindex(order).reset_index())
st.dataframe(pd.DataFrame({
    "Group": [g.split(" (")[0] for g in gt["Group label"]],
    f"{measure} range": [f"{fmt_v(a)} to {fmt_v(b)}" for a, b in zip(gt["lo"], gt["hi"])],
    "Typical zip code": [fmt_v(m) for m in gt["med"]],
    "Zip codes": gt["zips"],
}), hide_index=True, width="stretch")
pick = st.radio("Show the zip codes in group", order, horizontal=True)
sub = z[z["Group label"] == pick].sort_values(demo, ascending=False)
cols = ["Zip", "City", demo, "Total_Households"] + [f"{p} per HH" for p in f["programs"]]
show = sub[cols].round({"Total_Households": 0}).rename(columns={demo: u.DEMOGRAPHICS[demo], "Total_Households": "Households",
                                 **{f"{p} per HH": PER_HH_LABEL[p] for p in f["programs"]}})
st.dataframe(show, hide_index=True, width="stretch",
             column_config={**{c: st.column_config.NumberColumn(format="%.1f") for c in show.columns[2:]},
                            "Households": st.column_config.NumberColumn(format="localized")})
st.caption(f"{len(sub)} zip codes · " + u.filter_summary(f))
u.download(z.drop(columns=["Zip label"]), f"demographic_groups_{demo}")

with st.expander("About this view"):
    st.markdown(
        "- Demographics come from the American Community Survey 5-year estimates for each zip code.\n"
        "- Program values are monthly averages over the selected time period, divided by households.\n"
        "- 32 PO-box zip codes have no census data and are left out of this view.\n"
        "- Earlier analysis found the food bank link to LIHEAP holds mainly in high-poverty zip codes, while the "
        "CalFresh link is similar across groups.")
