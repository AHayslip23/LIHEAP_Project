"""Component 1: Geographic map with zip code filtering and metric selection."""
import pandas as pd
import plotly.express as px
import streamlit as st

import utils as u

st.set_page_config(page_title="Map", layout="wide")
st.title("Map: where is assistance concentrated?")
st.write("Each zip code is shaded by the metric you choose, summarized over the time period in the sidebar. "
         "Darker means more. Hover over a zip code for its numbers.")

f = u.sidebar_filters(program=False, default_period=("2023-01", "2023-07"))
panel = u.apply_filters(u.load_panel(), f)

# label: (column, unit, divisor applied to the monthly average)
METRICS = {
    "LIHEAP enrollment (households, monthly average)": ("LIHEAP", "", 1),
    "LIHEAP enrollment per 1,000 households": ("LIHEAP_per_1k_HH", "", 1),
    "CalFresh benefits ($, monthly average)": ("CalFresh", "$", 1),
    "CalFresh benefits per household ($, monthly)": ("CalFresh_per_1k_HH", "$/HH", 1000),
    "Food bank distribution (lb, monthly average)": ("FoodBank", "lb", 1),
    "Food bank pounds per household (monthly)": ("FoodBank_per_1k_HH", "lb/HH", 1000),
    "Poverty rate (%)": ("Poverty_Rate_Pct", "%", 1),
    "Unemployment rate (%)": ("Unemployment_Rate_Pct", "%", 1),
    "Median gross rent ($)": ("Median_Gross_Rent", "$", 1),
}
c1, c2 = st.columns([2, 1])
metric = c1.selectbox("Metric", list(METRICS))
col, unit, divisor = METRICS[metric]
highlight = c2.checkbox("Show only the filtered zip codes", value=bool(f["zips"]),
                        help="Off: all zip codes are shaded and your filtered zips are outlined in the table below.")



def summarize(df):
    z = df.groupby("Zip").agg(value=(col, "mean"), months=(col, "count")).reset_index()
    z = z[z["months"] > 0].copy()
    z["value"] = z["value"] / divisor
    z["City"] = z["Zip"].map(u.load_cities())
    return z


# "Show only filtered" maps the filtered zips; otherwise map every zip for the period and regime
by_zip = summarize(panel if highlight else u.apply_filters(u.load_panel(), {**f, "zips": []}))

geo = u.load_geojson()
geo_zips = {feat["properties"]["zip"] for feat in geo["features"]}
mapped = by_zip[by_zip["Zip"].isin(geo_zips)]

if mapped.empty:
    st.warning("No data for this metric with the current filters. LIHEAP zip-level data covers only "
               "January–July 2023, so widen the time period to include those months.")
else:
    fig = px.choropleth(mapped, geojson=geo, locations="Zip", featureidkey="properties.zip", color="value",
                        color_continuous_scale="Blues", hover_name="Zip",
                        hover_data={"City": True, "value": ":,.1f", "Zip": False}, labels={"value": metric})
    fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator")
    fig.update_traces(marker_line_color="white", marker_line_width=0.5)
    fig.update_layout(height=620, margin=dict(l=0, r=0, t=0, b=0),
                      coloraxis_colorbar=dict(title=unit or "households"))
    st.plotly_chart(fig, width="stretch")

    top = mapped.sort_values("value", ascending=False)
    k1, k2, k3 = st.columns(3)
    k1.metric("Zip codes shown", f"{len(mapped)}")
    k2.metric("Highest", f"{top.iloc[0]['Zip']} · {top.iloc[0]['City']}")
    k3.metric("County median", f"{mapped['value'].median():,.1f} {unit}")

missing = by_zip[~by_zip["Zip"].isin(geo_zips)]
if len(missing):
    st.caption(f"{len(missing)} zip codes with data have no map boundary (mostly PO-box zips) and appear only "
               "in the table below.")

st.subheader("Values by zip code")
st.caption(u.filter_summary(f))
table = by_zip.sort_values("value", ascending=False).rename(columns={"value": metric, "months": "Months of data"})
if f["zips"]:
    table["In your filter"] = table["Zip"].isin(f["zips"])
st.dataframe(table, width="stretch", hide_index=True,
             column_config={metric: st.column_config.NumberColumn(format="%.1f")})
u.download(table, "map_values_by_zip")

with st.expander("About this map"):
    st.markdown(
        "- **Monthly average** = the average of the months in your time period that have data for that zip code.\n"
        "- **Per household** values divide by the zip's household count (2019–2023 American Community Survey).\n"
        "- LIHEAP zip-level data covers January–July 2023 only. CalFresh covers 2020–2025 and food bank 2018–2025.\n"
        "- Food bank months reported as zero pounds are treated as missing.")
