"""
Automated check of every dashboard page and its main controls.

Run from the repository root:
    python test_dashboard.py

It starts each page in Streamlit's test harness (no browser needed), changes the filters and controls,
and reports any page that raises an error. The first run may take about a minute while the models train.
"""
import time
from pathlib import Path

from streamlit.testing.v1 import AppTest

HOME = str(Path(__file__).resolve().parent / "app" / "Home.py")
results = []


def run(at, label):
    t = time.time()
    at.run()
    secs = time.time() - t
    ok = not at.exception
    results.append(ok)
    msg = "" if ok else "  <-- " + at.exception[0].message[:200]
    print(f"{'PASS' if ok else 'FAIL'}  {secs:5.1f}s  {label}{msg}")
    return ok


at = AppTest.from_file(HOME, default_timeout=600)
run(at, "Home page")

# 1. Map
at.switch_page("pages/1_Map.py")
run(at, "Map: default")
for metric in at.selectbox[0].options:
    at.selectbox[0].set_value(metric)
    run(at, f"Map: metric '{metric}'")
at.sidebar.multiselect(key="w_cities").set_value(["Escondido"])
run(at, "Map: city filter = Escondido")

# 2. Time series (city filter should carry over)
at.switch_page("pages/2_Time_Series.py")
run(at, "Time Series: default")
carried = at.sidebar.multiselect(key="w_cities").value
print(f"      filter carried over from Map: {carried}")
results.append(carried == ["Escondido"])
at.radio[0].set_value("Per 1,000 households")
run(at, "Time Series: per 1,000 households")
at.sidebar.multiselect(key="w_regimes").set_value(["Emergency Allotments ended"])
run(at, "Time Series: regime filter")
[b for b in at.sidebar.button if b.label.startswith("Clear")][0].click()
run(at, "Time Series: clear filters button")

# Time period: the "2023" quick-pick should carry over to the next page
[b for b in at.sidebar.button if b.label == "2023"][0].click()
run(at, "Time Series: '2023' period button")

# 3. Policy timeline
at.switch_page("pages/3_Policy_Timeline.py")
run(at, "Policy Timeline: default")
period = at.sidebar.select_slider[0].value
print(f"      period carried over from Time Series: {period}")
results.append(tuple(period) == ("2023-01", "2023-12"))
[b for b in at.sidebar.button if b.label == "All"][0].click()
run(at, "Policy Timeline: 'All' period button")
at.selectbox[0].set_value("Food bank")
run(at, "Policy Timeline: overlay food bank")

# 4. Correlation explorer
at.switch_page("pages/4_Correlation_Explorer.py")
run(at, "Correlation Explorer: default")
print(f"      CalFresh, lag 1, Spearman = {at.metric[0].value} (expected 0.68)")
for lag in (0, 2, 3):
    at.select_slider[0].set_value(lag)
    run(at, f"Correlation Explorer: lag {lag}")
at.selectbox[0].set_value("Food bank")
at.radio[0].set_value("Per household")
run(at, "Correlation Explorer: food bank, per household")

# 5. Forecast
at.switch_page("pages/5_Forecast.py")
run(at, "Forecast: default (may train models on first run)")
at.radio[0].set_value("Food bank")
run(at, "Forecast: food bank")
at.number_input[0].set_value(100)
run(at, "Forecast: custom LIHEAP input")

# 6. Scenario analysis
at.switch_page("pages/6_Scenario_Analysis.py")
run(at, "Scenario: default")
at.slider[0].set_value(50)
run(at, "Scenario: slider to +50%")

# 7. Demographics
at.switch_page("pages/7_Demographics.py")
run(at, "Demographics: default")
at.selectbox[0].set_value("Unemployment_Rate_Pct")
run(at, "Demographics: unemployment")
at.radio[0].set_value(5)
run(at, "Demographics: fifths")

# 8. Policy impact
at.switch_page("pages/8_Policy_Impact.py")
run(at, "Policy Impact: default (Emergency Allotments end)")
for option in at.selectbox[0].options[::4]:
    at.selectbox[0].set_value(option)
    run(at, f"Policy Impact: {option[:50]}")

print(f"\n{sum(results)} of {len(results)} checks passed")
