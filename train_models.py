"""
Train the two deployment models used by the dashboard's forecast and scenario pages.
 
Run once from the app folder (and again whenever Predictive_Features.csv changes):
    python train_models.py
 
Saves models/scenario_models.joblib with both fitted models plus the metadata
the app needs (feature lists, interval widths, the months the models cover).
Settings are the ones chosen by time-aware CV in Predictive_Modeling.ipynb.
"""

#load in the libaries 
from pathlib import Path
 
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

#load in the data 
DATA_PATH = Path("data")/"Modeling"/"Predictive_Features.csv"
OUT = Path("models") / "scenario_models.joblib"

#define regression model features 
CORE = ["LIHEAP_lag1", "LIHEAP_lag2", "LIHEAP_lag3", "LIHEAP_lag1_per_1k_HH",
        "Log_Households", "Poverty_Rate", "Unemployment_Rate", "Median_Rent_k", "Pct_65_Plus", "LIHEAPxPoverty", "LIHEAPxRent", "Demo_Imputed"]

HISTORY = {
    "CalFresh_Dollars": ["CalFresh_lag1", "CalFresh_yoy_change_lag1"],
    "FoodBank_Pounds": ["oodBank_lag1", "FoodBank_yoy_change_lag1", "FoodBank_lag1_missing", "Pct_Single_Parent_HH"],
}

BOOLEAN = ["Demo_Imputed", "FoodBank_lag1_missing"]
LOG_DOLLARS = ["CalFresh_lag1", "FoodBank_lag1"]

#build linear regression pipeline
def linear_pipeline(features):
    log_cols = [c for c in features if c in LOG_DOLLARS]
    bool_cols = [c for c in features if c in BOOLEAN]
    num_cols = [c for c in features if c not in log_cols + bool_cols]
    pre = ColumnTransformer([
        ("log", Pipeline([("log1p", FunctionTransformer(np.log1p, features_names_out="one-to-one")),
                          ("scale", StandardScaler())]),
                          log_cols),
                          ("num", StandardScaler(), num_cols),
                          ("bool", "passthrough", bool_cols),
    ])
    return Pipeline([("preprocessor", pre), ("model", LinearRegression(fit_intercept=True, positive=True))])

#return the best model per target by CV RMSE (log), without policy indicators being included 
MODELS = {
    "CalFresh_Dollars": dict(
        name="Random Forest",
        make=lambda f: RandomForestRegressor(n_estimators=600, min_samples_leaf=1,
                                             max_samples=0.7, max_features=0.7, max_depth=None, random_state=42, n_jobs=-1)),
    "FoodBank_Pounds": dict(name="Linear Regression", make=linear_pipeline),
}

def model_rows(feats, targets):
    rows = feats[(feats["LIHEAP_lag1_observed"] == 1)].dropna(subset=[targets])
    features = [c for c in CORE + HISTORY[targets] if rows[c].nunique() > 1]
    return rows, features

def interval_half_width(rows, features, make, target, level=0.90):
    """Split-conformal width: 90th percentile of [log residual] from expanding-window folds."""
    months = sorted(rows["Month_Year"].unique())
    resid= []
    for i in range(2, len(months)):
        tr, va = rows[rows["Month_Year"].isin(months[:i])], rows[rows["Month_Year"] == months[i]]
        m = make(features).fit(tr[features].astype(float), np.log1p(tr[target]))
        resid.append(np.log1p(va[target]) - m.predict(va[features].astype(float)))
    return float(np.quantile(np.abs(np.concatenate(resid)), level))

def main():
    feats = pd.read_csv(DATA_PATH, dtype={"Zip Code": str})
    bundle = {}
    for target, spec in MODELS.items():
        rows, features = model_rows(feats, target)
        model = spec["make"](features).fit(rows[features].astype(float), np.log1p(rows[target]))
        q = interval_half_width(rows, features, spec["make"], target)
        bundle[target] = {
            "model": model,
            "model_name": spec["name"],
            "features": features,
            "half_width_log": q,
            "months": sorted(rows["Month_Year"].unique()),
        }
        print(f"{target}: {spec['name']} | {len(features)} features | {len(rows)} rows | "
              f"90% interval {np.exp(-q):.2f}x to {np.exp(q):.2f}x")
    OUT.parent.mkdir(exist_ok=True)
    joblib.dump(bundle, OUT)
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
