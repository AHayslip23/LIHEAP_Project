"""Component 6: Scenario analysis - "What if LIHEAP enrollment changes by X%?" """
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from scenario import (load_bundle, load_features, observed_liheap_range,
                      run_scenario, sensitivity_curve)

st.set_page_config(page_title="Scenario Analysis", layout="wide")

# Zip -> city lookup. Assistance_Spatial_FUll.csv covers every zip, including the PO-box zips
# that have no boundary in Zip_Segments.csv.
ZIP_INFO_PATH = Path(__file__).resolve().parents[2] / "data" / "Spatial" / "Assistance_Spatial_FUll.csv"
PROGRAMS = {"CalFresh_Dollars": "CalFresh benefits ($)", "FoodBank_Pounds": "Food bank food (lb)"}
UP, DOWN = "#2b6cb0", "#dd6b20"   # colorblind-safe blue / orange


@st.cache_resource(show_spinner="Loading models (the first run trains them, about a minute)...")
def get_bundle():
    return load_bundle()


@st.cache_data
def get_feats():
    return load_features()


@st.cache_data
def get_cities(po_box_zips):
    """City name per zip; PO-box zips (no census match) are marked so viewers know why they behave differently."""
    try:
        z = pd.read_csv(ZIP_INFO_PATH, usecols=["Zip_Code", "City"])
    except (FileNotFoundError, ValueError):
        return {}
    z["Zip_Code"] = z["Zip_Code"].astype(str).str.split(".").str[0].str.zfill(5)
    cities = z.dropna().drop_duplicates("Zip_Code").set_index("Zip_Code")["City"].to_dict()
    return {k: (f"{v} (PO box)" if k in po_box_zips else v) for k, v in cities.items()}


def month_label(m):
    return pd.to_datetime(m).strftime("%B %Y")


bundle, feats = get_bundle(), get_feats()
cities = get_cities(frozenset(feats.loc[feats["Demo_Imputed"] == 1, "Zip Code"]))
zip_label = lambda z: f"{z} · {cities[z]}" if z in cities else z

# ---------------------------------------------------------------- header
st.title("What if LIHEAP enrollment changes?")
st.write("Move the slider to see how the model's estimate of food assistance would change if LIHEAP "
         "energy-assistance enrollment had been higher or lower. Everything else about each zip code stays the same.")

# ---------------------------------------------------------------- sidebar controls
with st.sidebar:
    st.header("Scenario settings")
    target = st.radio("Program", list(PROGRAMS), format_func=PROGRAMS.get)
    months = bundle[target]["months"]
    month = st.selectbox("Month of data", months, index=len(months) - 1, format_func=month_label,
                         help="The model estimates this month's totals using the previous month's data.")
    pct = st.slider("Change in LIHEAP enrollment (%)", -50, 100, 10, step=5,
                    help="+10 means 10% more households enrolled in LIHEAP than actually were.")
    all_zips = sorted(feats.loc[feats["Month_Year"] == month, "Zip Code"].unique())
    zips = st.multiselect("Focus on specific zip codes (optional)", all_zips, format_func=zip_label)
    only_selected = st.checkbox("Change enrollment only in these zip codes", value=False, disabled=not zips)

table, summary = run_scenario(bundle, feats, target, month, pct, zips=zips or None,
                              changed_zips=zips if (zips and only_selected) else None)
is_dollars = target == "CalFresh_Dollars"
unit = "$" if is_dollars else "lb"
fmt = (lambda v: f"${v:,.0f}") if is_dollars else (lambda v: f"{v:,.0f} lb")
short = (lambda v: f"${v / 1e6:,.1f}M" if abs(v) >= 1e6 else f"${v / 1e3:,.0f}K") if is_dollars else \
        (lambda v: f"{v / 1e6:,.2f}M lb" if abs(v) >= 1e6 else f"{v / 1e3:,.0f}K lb")
program = "CalFresh benefits" if is_dollars else "food bank distribution"
area = "the selected zip codes" if zips else "San Diego County"
md = lambda text: text.replace("$", "\\$")   # stop Markdown reading $ as math

# ---------------------------------------------------------------- headline numbers
c1, c2, c3, c4 = st.columns(4)
c1.metric("Estimate with actual enrollment", fmt(summary["baseline_total"]))
c2.metric(f"Estimate with {pct:+d}% enrollment", fmt(summary["scenario_total"]), f"{summary['change_pct']:+.2f}%")
c3.metric("Difference", fmt(summary["change_total"]))
c4.metric("Zip codes affected", f"{summary['zips_changed']} of {summary['zips']}")

# ---------------------------------------------------------------- plain-language takeaway
size = abs(summary["change_pct"])
verdict = "effectively no change" if size < 1 else ("a small change" if size < 5 else "a noticeable change")
q = bundle[target]["half_width_log"]
st.info(
    f"**Takeaway:** a {pct:+d}% change in LIHEAP enrollment shifts estimated {program} in {area} by "
    f"**{summary['change_pct']:+.2f}%** ({md(short(summary['change_total']))} out of {md(short(summary['baseline_total']))}) "
    f"in {month_label(month)}: **{verdict}**. For comparison, the model's estimate for a single zip code is "
    f"typically within about {100 * (1 - np.exp(-q)):.0f}% below to {100 * (np.exp(q) - 1):.0f}% above the real value, "
    "so LIHEAP enrollment is a much weaker driver than each zip's own recent history."
)

if table["Scenario LIHEAP (lag 1)"].max() > observed_liheap_range(feats):
    st.warning("This scenario pushes some zip codes above the highest LIHEAP enrollment in the data, "
               "so their estimates are less reliable.")

# ---------------------------------------------------------------- charts
left, right = st.columns(2)
with left:
    st.subheader(f"How the total responds to bigger or smaller changes")
    curve = sensitivity_curve(bundle, feats, target, month, zips=zips or None)
    lim = max(10, curve["Change %"].abs().max() * 1.2)
    fig = px.line(curve, x="LIHEAP change %", y="Change %", markers=True,
                  labels={"LIHEAP change %": "Change in LIHEAP enrollment (%)",
                          "Change %": f"Change in estimated {program} (%)"})
    fig.update_yaxes(range=[-lim, lim], zeroline=True, zerolinecolor="#999")
    fig.add_vline(x=pct, line_dash="dot", line_color="#b42318",
                  annotation_text="Your scenario", annotation_position="top")
    st.plotly_chart(fig, width="stretch")
    note = ("The line stays close to zero across the whole range: even doubling or halving enrollment moves the "
            "county total by only a few percent.")
    if is_dollars:
        note += (" Its small bends come from how the Random Forest model splits the data into steps, "
                 "not from a real effect of LIHEAP.")
    st.caption(note)

with right:
    st.subheader("Zip codes with the largest changes")
    top = table.reindex(table["Change"].abs().sort_values(ascending=False).index).head(12).copy()
    top["Zip code"] = top["Zip Code"].map(zip_label)
    top["Direction"] = np.where(top["Change"] >= 0, "Increase", "Decrease")
    fig2 = px.bar(top, x="Change", y="Zip code", orientation="h", color="Direction",
                  color_discrete_map={"Increase": UP, "Decrease": DOWN},
                  labels={"Change": f"Change in estimate ({unit})"})
    fig2.update_yaxes(type="category", categoryorder="array", categoryarray=list(top["Zip code"]),
                      autorange="reversed", title=None)   # largest change at the top
    fig2.update_layout(legend_title_text=None)
    st.plotly_chart(fig2, width="stretch")
    st.caption("Each bar is a zip code's estimated change. Small moves in the opposite direction "
               "are model noise, not evidence that more LIHEAP enrollment reduces assistance.")

# ---------------------------------------------------------------- table + download
st.subheader("Results by zip code")
show = pd.DataFrame({
    "Zip code": table["Zip Code"],
    "City": table["Zip Code"].map(cities).fillna(""),
    "Estimate (actual enrollment)": table["Baseline forecast"],
    f"Estimate ({pct:+d}% enrollment)": table["Scenario forecast"],
    "Difference": table["Change"],
    "Difference %": table["Change %"],
})
money = "${:,.0f}" if is_dollars else "{:,.0f}"
st.dataframe(show.style.format({c: money for c in show.columns[2:5]} | {"Difference %": "{:+.2f}%"}),
             width="stretch", hide_index=True)
full = table.assign(City=table["Zip Code"].map(cities).fillna(""))
st.download_button("Download full results (CSV)", full.to_csv(index=False).encode(),
                   file_name=f"scenario_{target}_{month}_{pct:+d}pct.csv", mime="text/csv")

with st.expander("How this works"):
    st.markdown(
        f"- **Model:** {bundle[target]['model_name']}, chosen as the most accurate of three model types in "
        "time-ordered cross-validation (see the Predictive Model Evaluation Report).\n"
        "- **Inputs:** each zip code's LIHEAP enrollment over the previous three months, last month's "
        f"{program}, and census demographics (poverty, unemployment, rent, household count).\n"
        "- **Scenario:** every LIHEAP input is multiplied by (1 + your % / 100); all other inputs keep their real values.\n"
        "- **Uncertainty:** the 90% range in the downloaded file comes from the model's errors on months it had "
        "not seen (split-conformal intervals).\n"
        "- **Limits:** the model was trained on February–August 2023 only. It shows how sensitive the model is "
        "to LIHEAP, not a measured causal effect of enrolling more households."
    )
