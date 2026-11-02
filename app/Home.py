import streamlit as st

import utils as u

st.set_page_config(page_title="LIHEAP & Food Assistance", layout="wide")

st.title("LIHEAP & Food Assistance Dashboard")
st.write(
    "How does LIHEAP energy-assistance enrollment relate to CalFresh benefits and food bank distribution across "
    "San Diego County zip codes? Use the pages in the left sidebar to explore where assistance is concentrated, how "
    "it changed over time and around policy changes, and what the predictive model expects."
)

panel = u.load_panel()
first, last = u.month_label(panel["Month"].min()), u.month_label(panel["Month"].max())
c1, c2, c3, c4 = st.columns(4)
c1.metric("Zip codes", f"{panel['Zip'].nunique()}")
c1.caption("Across San Diego County")
c2.metric("Months of data", f"{panel['Month'].nunique()}")
c2.caption(f"{first} – {last}")
c3.metric("Months of LIHEAP data", "7")
c3.caption("Jan 2023 – Jul 2023 (zip-level)")
c4.metric("Policy changes tracked", f"{len(u.load_events())}")
c4.caption("LIHEAP, CalFresh and food banks")

st.subheader("Pages")
st.markdown(
    """
| Page | What it answers |
|---|---|
| **Map** | Which zip codes have the most enrollment, benefits or need? |
| **Time Series** | How have the three programs changed month to month? |
| **Policy Timeline** | Which policy changes happened when, and what did they coincide with? |
| **Correlation Explorer** | How closely does LIHEAP enrollment track CalFresh and food bank, and at what lag? |
| **Forecast** | What does the predictive model expect for each zip code, and how accurate is it? |
| **Scenario Analysis** | What if LIHEAP enrollment were X% higher or lower? |
| **Demographics** | How does assistance differ by poverty, unemployment, rent and more? |
| **Policy Impact** | How did each program change in the months before vs after a policy change? |
"""
)

st.subheader("Filters")
st.write("Each page's sidebar has filters for **program type**, **time period**, **policy regime**, **city** and "
         "**zip code**. Your choices carry over when you switch pages, and every page has a **Download** button for "
         "the data behind its charts.")

st.subheader("Key findings")
st.markdown(
    "- LIHEAP enrollment tracks CalFresh dollars closely (Spearman ρ ≈ 0.64–0.70) and food bank pounds moderately "
    "(ρ ≈ 0.46). It shows **where** food assistance is needed more than **when** it will rise.\n"
    "- The food bank link holds mainly in high-poverty zip codes; the CalFresh link is similar across groups.\n"
    "- CalFresh benefits fell about 39% county-wide when Emergency Allotments ended in April 2023.\n"
    "- For month-ahead forecasts, last month's value is the strongest predictor; LIHEAP adds little on top of it.")

st.subheader("Data sources")
st.markdown(
    "- **LIHEAP:** validated zip-level enrollment counts, San Diego County, January–July 2023.\n"
    "- **CalFresh:** monthly benefit dollars by zip code, 2020–2025.\n"
    "- **Food banks:** monthly pounds distributed by Feeding San Diego and the San Diego Food Bank, 2018–2025.\n"
    "- **Demographics:** U.S. Census American Community Survey 5-year estimates by zip code.\n"
    "- **Policy changes:** federal and state LIHEAP, CalFresh and food bank policy events compiled for this project.")
st.caption("A San Diego Data Science Alliance project.")
