"""
Scenario engine: "What if LIHEAP enrollment changes by X%?"
 
How a scenario is built
-----------------------
Every LIHEAP input the models use is proportional to prior-month LIHEAP enrollment:
    LIHEAP_lag1, LIHEAP_lag2, LIHEAP_lag3   (enrollment counts)
    LIHEAP_lag1_per_1k_HH                   (lag 1 / households x 1,000)
    LIHEAPxPoverty, LIHEAPxRent             (lag 1 x centered poverty / rent)
so an X% change in enrollment multiplies each of them by (1 + X/100). All other inputs
(last month's CalFresh / food bank values, demographics) stay as observed.
Both models predict log1p(value); predictions are converted back with expm1.
"""

from pathlib import Path
import joblib 
import numpy as np
import pandas as pd 

APP_DIR = Path(__file__).resolve().parent
MODEL_PATH = APP_DIR / "models" / "scenario_models.joblib"
DATA_PATH = APP_DIR.parent / "data" / "Modeling" / "Predictive_Features.csv"

#define lIHEAP scaled features
LIHEAP_SCALED = ["LIHEAP_lag1", "LIHEAP_lag2", "LIHEAP_lag3", "LIHEAP_lag1_per_1k_HH", "LIHEAPxPoverty", "LIHEAPxRent"]

#define target labels 
TARGET_LABELS = {
    "CalFresh_Dollars": "CalFresh dollars",
    "FoodBank_Pounds": "Food bank pounds"
}

def load_bundle(path=MODEL_PATH):
    """Load the trained models. If the file is missing (first run, fresh deploy) or was saved
    by an incompatible scikit-learn version, retrain with train_models.py and load again."""
    if Path(path).exists():
        try:
            return joblib.load(path)
        except Exception:
            pass
    import train_models
    train_models.main()
    return joblib.load(path)

def load_features(path=DATA_PATH):
    return pd.read_csv(path, dtype={"Zip Code": str})

def apply_liheap_change(rows, pct_change, zips=None):
    """Return a copy of rows with LIHEAP inputs scaled by (1 + pct_change/100).
    If zips is given, only those zip codes are changed (the rest stay at baseline)."""
    out = rows.copy()
    mask = out["Zip Code"].isin(zips) if zips else pd.Series(True, index=out.index)
    factor = 1 + pct_change / 100
    for col in LIHEAP_SCALED:
        out.loc[mask, col] = out.loc[mask, col] * factor
    return out

def predict(bundle_entry, rows):
    X = rows[bundle_entry["features"]].astype(float)
    pred_log = bundle_entry["model"].predict(X)
    q = bundle_entry["half_width_log"]
    return pd.DataFrame({
          "pred": np.expm1(pred_log),
          "lower": np.expm1(pred_log - q),
          "upper": np.expm1(pred_log + q)}, index=rows.index)

def run_scenario(bundle, feats, target, month, pct_change, zips=None, changed_zips=None):
    """Baseline vs scenario predictions for one target and month.
    target       : "CalFresh_Dollars" or "FoodBank_Pounds"
    month        : "YYYY-MM" (must be a month the model covers, e.g. "2023-08")
    pct_change   : e.g. 10 for +10%, -25 for -25%
    zips         : limit the results to these zip codes (None = all)
    changed_zips : apply the LIHEAP change only to these zips (None = all shown zips)
    Returns (zip_table, summary_dict)."""
    entry=bundle[target]
    rows = feats[(feats["Month_Year"] == month) & (feats["LIHEAP_lag1_observed"] == 1)]
    rows = rows.dropna(subset=entry["features"])
    if zips:
        rows = rows[rows["Zip Code"].isin(zips)]
    if rows.empty:
        raise ValueError(f"No rows found for the given zips: {zips}")
    base = predict(entry, rows)
    scen = predict(entry, apply_liheap_change(rows, pct_change, changed_zips))
    table = pd.DataFrame({
                "Zip Code": rows["Zip Code"].values,
                "LIHEAP enrollment (lag 1)": rows["LIHEAP_lag1"].values,
                "Scenario LIHEAP (lag 1)": rows["LIHEAP_lag1"].values * (1 + pct_change / 100),
                "Actual": rows[target].values,
                "Baseline forecast": base["pred"].values,
                "Scenario forecast": scen["pred"].values,
                "Scenario low 90%": scen["lower"].values,
                "Scenario high 90%": scen["upper"].values,
        })
    
    if changed_zips:
        table.loc[~table["Zip Code"].isin(changed_zips), "Scenario LIHEAP (lag 1)"] = table["LIHEAP enrollment (lag 1)"]

    table["Change"] = table["Scenario forecast"] - table["Baseline forecast"]
    table["Change %"] = 100 * table["Change"] / table["Baseline forecast"]
    table = table.sort_values("Change", ascending=False).reset_index(drop=True)

    b, s = table["Baseline forecast"].sum(), table["Scenario forecast"].sum()
    summary = {
        "target": target,
        "model": entry["model_name"],
        "month": month,
        "pct_change": pct_change,
        "zips": len(table),
        "baseline_total": b,
        "scenario_total": s,
        "change_total": s - b,
        "change_pct": 100 * (s - b) / b,
        "zips_changed": int((table["Change"].abs() > 1e-9).sum()),
    }
    return table, summary


def sensitivity_curve(bundle, feats, target, month, pct_range=range(-50, 101, 10), zips=None):
    """County (or selected-zip) total forecast across a range of LIHEAP changes."""
    rows = []
    for p in pct_range:
        _, s = run_scenario(bundle, feats, target, month, p, zips=zips)
        rows.append({
                "LIHEAP change %": p,
                "Forecast total": s["scenario_total"],
                "Change %": s["change_pct"]
        })
    return pd.DataFrame(rows)

def observed_liheap_range(feats):
    """Largest LIHEAP_lag1 seen in training; scenarios beyond it are extrapolation."""
    return float(feats.loc[feats["LIHEAP_lag1_observed"] == 1, "LIHEAP_lag1"].max())
                





     
