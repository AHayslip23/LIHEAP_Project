"""
Shared data loading, filters and helpers for every dashboard page.

Data sources (all under data/):
    Spatial/Assistance_Spatial_FUll.csv   zip-by-month LIHEAP, CalFresh, food bank + census demographics
    Policy_TimeLag/TimeLag_PolicyAnnotated.csv   LIHEAP enrollment with 1-3 month lags (2023)
    Policy_TimeLag/Policy_Events.csv      policy changes with effective dates
    Spatial/SD_Zipcodes_simplified.geojson   zip boundaries for the map
"""
import inspect
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
DATA = APP_DIR.parent / "data"

# ---------------------------------------------------------------- programs and labels
PROGRAMS = {
    "LIHEAP": {"col": "LIHEAP", "label": "LIHEAP enrollment (households)", "unit": "households", "color": "#2b6cb0"},
    "CalFresh": {"col": "CalFresh", "label": "CalFresh benefits ($)", "unit": "$", "color": "#2f855a"},
    "Food bank": {"col": "FoodBank", "label": "Food bank distribution (lb)", "unit": "lb", "color": "#dd6b20"},
}
PROGRAM_POLICY_NAME = {"LIHEAP": "LIHEAP", "CalFresh": "CalFresh", "Food bank": "FoodBank"}

DEMOGRAPHICS = {
    "Poverty_Rate_Pct": "Poverty rate (%)",
    "Unemployment_Rate_Pct": "Unemployment rate (%)",
    "Median_Gross_Rent": "Median gross rent ($)",
    "Pct_65_Plus": "Residents aged 65+ (%)",
    "Single_Parent_per_1k_HH": "Single-parent households per 1,000",
}

# Policy regimes used for filtering (from Policy_Events.csv)
REGIMES = [
    ("Before pandemic", "2018-01", "2020-02"),
    ("Pandemic emergency provisions", "2020-03", "2023-03"),
    ("Emergency Allotments ended", "2023-04", "2023-06"),
    ("Work rules resumed", "2023-07", "2025-06"),
    ("2025 work-rule expansion", "2025-07", "2099-12"),
]
REGIME_NAMES = [r[0] for r in REGIMES]


def regime_of(month: str) -> str:
    for name, start, end in REGIMES:
        if start <= month <= end:
            return name
    return REGIME_NAMES[-1]


def month_label(m: str) -> str:
    return pd.to_datetime(m).strftime("%b %Y")


def fmt_value(v, unit):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    if unit == "$":
        return f"${v:,.0f}"
    if unit == "lb":
        return f"{v:,.0f} lb"
    return f"{v:,.0f}"


def short_value(v, unit):
    """Compact number for sentences, with $ escaped so Markdown doesn't treat it as math."""
    a = abs(v)
    s = f"{v / 1e6:,.1f}M" if a >= 1e6 else (f"{v / 1e3:,.0f}K" if a >= 1e4 else f"{v:,.0f}")
    return f"\\${s}" if unit == "$" else (f"{s} lb" if unit == "lb" else s)


# ---------------------------------------------------------------- data loaders (cached)
@st.cache_data
def load_panel() -> pd.DataFrame:
    """Zip-by-month panel with one column per program plus demographics and city."""
    d = pd.read_csv(DATA / "Spatial" / "Assistance_Spatial_FUll.csv", low_memory=False)
    d["Zip"] = d["Zip_Code"].astype(str).str.split(".").str[0].str.zfill(5)
    d = d.rename(columns={"Month Year": "Month", "Calfresh_Dollars": "CalFresh",
                          "LIHEAP_Enrollment_Count": "LIHEAP", "Total_Pounds_Distributed": "FoodBank"})
    d = d.dropna(subset=["Month"])
    d["Month"] = d["Month"].astype(str)
    # Zero food bank pounds means no reporting that month, not zero distribution
    d.loc[d["FoodBank"] == 0, "FoodBank"] = np.nan
    # LIHEAP zip-level data is reliable only Jan-Jul 2023 (later records mostly lack a zip)
    d.loc[(d["Month"] < "2023-01") | (d["Month"] > "2023-07"), "LIHEAP"] = np.nan
    hh = d["Total_Households"]
    d["Pct_65_Plus"] = 100 * d["Population_65_Plus"] / d["Total_Population"]
    d["Single_Parent_per_1k_HH"] = 1000 * (d["Single_Mother_Households_With_Own_Children_Under18"]
                                           + d["Single_Father_Households_With_Own_Children_Under18"]) / hh
    for p in ("LIHEAP", "CalFresh", "FoodBank"):
        d[f"{p}_per_1k_HH"] = 1000 * d[p] / hh
    d["Regime"] = d["Month"].map(regime_of)
    keep = ["Zip", "City", "Month", "Regime", "LIHEAP", "CalFresh", "FoodBank",
            "LIHEAP_per_1k_HH", "CalFresh_per_1k_HH", "FoodBank_per_1k_HH",
            "Total_Population", "Total_Households", *DEMOGRAPHICS]
    return d[keep].sort_values(["Month", "Zip"]).reset_index(drop=True)


@st.cache_data
def load_cities() -> dict:
    p = load_panel()
    return p.dropna(subset=["City"]).drop_duplicates("Zip").set_index("Zip")["City"].to_dict()


@st.cache_data
def load_events() -> pd.DataFrame:
    e = pd.read_csv(DATA / "Policy_TimeLag" / "Policy_Events.csv")
    e["program"] = e["program"].replace({"FoodBank": "Food bank"})
    e["Start"] = pd.to_datetime(e["start_month"])
    e["End"] = pd.to_datetime(e["end_month"]) + pd.offsets.MonthEnd(0)
    return e


@st.cache_data
def load_lags() -> pd.DataFrame:
    """2023 zip-months with LIHEAP enrollment at lags 0-3 joined to CalFresh and food bank."""
    t = pd.read_csv(DATA / "Policy_TimeLag" / "TimeLag_PolicyAnnotated.csv")
    t["Zip"] = t["Zip Code"].astype(str).str.split(".").str[0].str.zfill(5)
    t = t.rename(columns={"Month_Year": "Month", "Enrollment_Count": "LIHEAP_lag0"})
    t = t[["Zip", "Month", "LIHEAP_lag0", "LIHEAP_lag1", "LIHEAP_lag2", "LIHEAP_lag3"]]
    p = load_panel()
    full = pd.read_csv(DATA / "Spatial" / "Assistance_Spatial_FUll.csv", low_memory=False,
                       usecols=["Zip_Code", "Month Year", "Calfresh_Dollars", "Total_Pounds_Distributed",
                                "Total_Households"])
    full["Zip"] = full["Zip_Code"].astype(str).str.split(".").str[0].str.zfill(5)
    full = full.rename(columns={"Month Year": "Month", "Calfresh_Dollars": "CalFresh",
                                "Total_Pounds_Distributed": "FoodBank"}).dropna(subset=["Month"])
    full.loc[full["FoodBank"] == 0, "FoodBank"] = np.nan
    out = t.merge(full[["Zip", "Month", "CalFresh", "FoodBank", "Total_Households"]], on=["Zip", "Month"], how="left")
    out["City"] = out["Zip"].map(p.drop_duplicates("Zip").set_index("Zip")["City"])
    return out


@st.cache_data
def load_geojson() -> dict:
    with open(DATA / "Spatial" / "SD_Zipcodes_simplified.geojson") as f:
        return json.load(f)


def zip_label(z: str) -> str:
    c = load_cities().get(z)
    return f"{z} · {c}" if c else z


# ---------------------------------------------------------------- shared sidebar filters
def _persist(key, default, valid=lambda v: True):
    """Keep a filter's value when moving between pages.

    Streamlit clears widget state on page change, so each filter's value is also stored under a plain key
    and copied back into the widget's key before the widget is drawn."""
    wkey = f"w_{key}"
    saved = st.session_state.get(key, st.session_state.get(wkey, default))
    st.session_state[wkey] = saved if valid(saved) else default
    return wkey


def _save(key):
    st.session_state[key] = st.session_state[f"w_{key}"]


def _clear_filters():
    for k in ("cities", "zips", "regimes"):
        st.session_state[k] = []
        st.session_state[f"w_{k}"] = []


def _set_period(lo, hi):
    """Quick-pick buttons: store the new period and start a fresh slider (new key) that opens at it."""
    st.session_state["period"] = (lo, hi)
    st.session_state["period_version"] = st.session_state.get("period_version", 0) + 1


def sidebar_filters(program=True, multi_program=True, period=True, regime=True, zips=True,
                    month_range=("2018-01", "2025-08"), default_programs=("LIHEAP", "CalFresh", "Food bank")):
    """Render the shared filters. Returns a dict with only the filters this page uses."""
    out = {}
    p = load_panel()
    months = sorted(m for m in p["Month"].unique() if month_range[0] <= m <= month_range[1])
    with st.sidebar:
        st.header("Filters")
        if program:
            if multi_program:
                k = _persist("programs", list(default_programs),
                             valid=lambda v: isinstance(v, list) and all(x in PROGRAMS for x in v))
                out["programs"] = st.multiselect("Program type", list(PROGRAMS), key=k,
                                                 on_change=_save, args=("programs",)) or list(default_programs)
            else:
                k = _persist("program", default_programs[0], valid=lambda v: v in PROGRAMS)
                out["program"] = st.radio("Program type", list(PROGRAMS), key=k, on_change=_save, args=("program",))
        if period:
            # One shared time period for every page (default: all months). The slider gets a key per page and
            # starts from the stored period, so the choice made on one page carries over to the next.
            saved = st.session_state.get("period")
            if not (isinstance(saved, (tuple, list)) and len(saved) == 2 and saved[0] <= saved[1]):
                saved = (months[0], months[-1])
            lo = min(max(saved[0], months[0]), months[-1])
            hi = max(min(saved[1], months[-1]), months[0])
            lo = next(m for m in months if m >= lo)
            hi = [m for m in months if m <= hi][-1]
            # Key per page (and per quick-pick click): a new key makes Streamlit draw a fresh slider at value=(lo, hi)
            wkey = f"w_period_{Path(inspect.stack()[1].filename).stem}_{st.session_state.get('period_version', 0)}"
            out["period"] = tuple(st.select_slider("Time period", options=months, value=(lo, hi), key=wkey,
                                                   format_func=month_label))
            st.session_state["period"] = out["period"]
            b1, b2, b3 = st.columns(3)
            b1.button("All", on_click=_set_period, args=(months[0], months[-1]), width="stretch",
                      help=f"{month_label(months[0])} – {month_label(months[-1])}")
            b2.button("2023", on_click=_set_period, args=("2023-01", "2023-12"), width="stretch",
                      help="Jan – Dec 2023, the year with zip-level LIHEAP data (Jan – Jul)")
            last12 = months[-12] if len(months) >= 12 else months[0]
            b3.button("1 year", on_click=_set_period, args=(last12, months[-1]), width="stretch",
                      help=f"{month_label(last12)} – {month_label(months[-1])}")
            st.caption("The same time period applies on every page.")
        if regime:
            k = _persist("regimes", [])
            out["regimes"] = st.multiselect("Policy regime (blank = all)", REGIME_NAMES, key=k,
                                            on_change=_save, args=("regimes",),
                                            help="Periods between major CalFresh policy changes.")
        if zips:
            all_zips = sorted(p["Zip"].unique())
            cities = sorted(set(load_cities().values()))
            kc = _persist("cities", [])
            sel_cities = st.multiselect("City (blank = all)", cities, key=kc, on_change=_save, args=("cities",))
            kz = _persist("zips", [])
            st.session_state[kz] = [z for z in st.session_state[kz] if z in all_zips]
            sel_zips = st.multiselect("Zip code (blank = all)", all_zips, key=kz, format_func=zip_label,
                                      on_change=_save, args=("zips",))
            chosen = set(sel_zips)
            if sel_cities:
                chosen |= {z for z, c in load_cities().items() if c in sel_cities}
            out["zips"] = sorted(chosen)
        if any(st.session_state.get(k) for k in ("cities", "zips", "regimes")):
            st.button("Clear zip, city and regime filters", on_click=_clear_filters)
        st.caption("Filters carry over when you switch pages.")
    return out


def apply_filters(df, f, month_col="Month", zip_col="Zip"):
    out = df
    if f.get("period"):
        lo, hi = f["period"]
        out = out[(out[month_col] >= lo) & (out[month_col] <= hi)]
    if f.get("regimes"):
        out = out[out[month_col].map(regime_of).isin(f["regimes"])]
    if f.get("zips"):
        out = out[out[zip_col].isin(f["zips"])]
    return out


def filter_summary(f) -> str:
    parts = []
    if f.get("period"):
        parts.append(f"{month_label(f['period'][0])} – {month_label(f['period'][1])}")
    if f.get("regimes"):
        parts.append("regimes: " + ", ".join(f["regimes"]))
    parts.append(f"{len(f['zips'])} selected zip codes" if f.get("zips") else "all zip codes")
    return " · ".join(parts)


def download(df: pd.DataFrame, name: str, label="Download this data (CSV)"):
    st.download_button(label, df.to_csv(index=False).encode(), file_name=f"{name}.csv", mime="text/csv",
                       key=f"dl_{name}")


def add_policy_lines(fig, events, programs, start, end, row=None):
    """Draw dotted lines at policy start dates for the chosen programs within the date range."""
    ev = events[events["program"].isin(programs)]
    ev = ev[(ev["Start"] >= pd.to_datetime(start)) & (ev["Start"] <= pd.to_datetime(end) + pd.offsets.MonthEnd(0))]
    for when, grp in ev.groupby("Start"):
        name = "; ".join(sorted(set(grp["policy"])))
        kw = dict(x=when.timestamp() * 1000, line_dash="dot", line_color="#b42318", line_width=1)
        if row is None:
            fig.add_vline(**kw)
        else:
            fig.add_vline(row=row, col=1, **kw)
    return ev.drop_duplicates(["policy", "Start"])


# ---------------------------------------------------------------- statistics (no scipy needed)
def _norm_sf(z):
    return 0.5 * math.erfc(z / math.sqrt(2))


def correlation(x, y, method="spearman"):
    """Correlation with Fisher-z 95% CI and two-sided p-value (normal approximation)."""
    m = pd.concat([pd.Series(x), pd.Series(y)], axis=1).dropna()
    n = len(m)
    if n < 5:
        return {"r": np.nan, "lo": np.nan, "hi": np.nan, "p": np.nan, "n": n}
    r = m.iloc[:, 0].corr(m.iloc[:, 1], method=method)
    r_c = max(min(r, 0.999999), -0.999999)
    z, se = math.atanh(r_c), 1 / math.sqrt(n - 3)
    if method == "spearman":
        se *= math.sqrt(1 + r_c ** 2 / 2)  # Bonett-Wright adjustment
    return {"r": r, "lo": math.tanh(z - 1.96 * se), "hi": math.tanh(z + 1.96 * se),
            "p": 2 * _norm_sf(abs(z) / se), "n": n}


def strength(r):
    a = abs(r)
    return "very weak" if a < 0.2 else "weak" if a < 0.4 else "moderate" if a < 0.6 else "strong" if a < 0.8 else "very strong"


# ---------------------------------------------------------------- chart helpers
def compact(v, unit=""):
    """1234567 -> '1.2M', with $ or lb attached."""
    a = abs(v)
    s = (f"{v / 1e6:.1f}M" if a >= 1e6 else f"{v / 1e3:.0f}K" if a >= 1e3 else f"{v:.0f}" if a >= 1 else f"{v:.2g}")
    s = s.replace(".0M", "M")
    return f"${s}" if unit == "$" else (f"{s} lb" if unit == "lb" else s)


def log_ticks(values, unit=""):
    """Readable tick marks for a log axis: 1, 2, 5, 10, 20, 50 ... within the data range."""
    v = pd.Series(values).dropna()
    v = v[v > 0]
    if v.empty:
        return {}
    lo, hi = math.floor(math.log10(v.min())), math.ceil(math.log10(v.max()))
    ticks = [m * 10 ** e for e in range(lo, hi + 1) for m in (1, 2, 5) if v.min() / 2 <= m * 10 ** e <= v.max() * 2]
    if len(ticks) > 8:
        ticks = [t for t in ticks if str(int(t) if t >= 1 else t).lstrip("0.").startswith("1")]
    return dict(type="log", tickvals=ticks, ticktext=[compact(t, unit) for t in ticks], minor=dict(showgrid=False))


def style_fig(fig, height=360):
    """Consistent clean look for every chart."""
    fig.update_layout(template="plotly_white", height=height, margin=dict(l=10, r=10, t=40, b=10),
                      font=dict(size=13), hoverlabel=dict(font_size=13),
                      legend=dict(orientation="h", y=1.08, x=0, title_text=""))
    fig.update_xaxes(showline=True, linecolor="#cbd5e0", ticks="outside", tickcolor="#cbd5e0")
    fig.update_yaxes(showline=False, gridcolor="#edf2f7", zeroline=False)
    return fig
