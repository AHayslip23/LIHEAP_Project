# LIHEAP_Project

Statistical analysis of how LIHEAP energy-assistance enrollment correlates with CalFresh and food bank distribution across San Diego County zip codes (2023): lag effects, policy-period shifts, demographic segments and sensitivity testing.

A San Diego Data Science Alliance project. The final write-up is in [`reports/Correlation_StatisticalReport.pdf`](reports/Correlation_StatisticalReport.pdf).

## Key findings

- LIHEAP enrollment tracks CalFresh dollars closely (Spearman ρ up to 0.70) and food bank pounds moderately (ρ ≈ 0.46).
- No time lag (0–3 months) is clearly best: LIHEAP marks *where* food assistance is needed more than *when*.
- Correlations held through every 2023 policy change and when any single month was dropped.
- Per household, correlations fall by 0.10–0.20 but stay moderate; the food bank link holds only in high-poverty zip codes.

## Pipeline

Run the notebooks in `notebooks/` in this order, with `notebooks/` as the working directory (the default when you open a notebook in Jupyter or VS Code). Each reads and writes its datasets in `data/` (by subfolder) and saves charts to `figures/`.

| Step | Notebook | Main output |
|---|---|---|
| 1 | `Data Cleaning LIHEAP.ipynb` | `LIHEAP/LIHEAP_validated.csv` |
| 2 | `Calfresh Data Cleaning.ipynb` | `CalFresh/CalFresh_cleaned.csv` |
| 3 | `Food Banks Data Cleaning.ipynb` | `Food Bank/FoodBank_cleaned.csv` |
| 4 | `Coverage Matrix + Standardization of Data Sets.ipynb` | `Integrated/Assistance_Integrated.csv` |
| 5 | `Census_Demographic_Pull.ipynb` | `ACS/Demographics_SD_ZipCode.csv` |
| 6 | `Merge of Census and Integrated Datasets.ipynb` | `Integrated/Assistance_Demographics_Master.csv` |
| 7 | `Notebook for Policy Annotations.ipynb` | `Policy_TimeLag/Policy_Annotations.csv` |
| 8 | `TimeLag_Generation.ipynb` | `LIHEAP/LIHEAP_lags.csv` |
| 9 | `Merge LIHEAP and Policy Annotation.ipynb` | `Policy_TimeLag/TimeLag_PolicyAnnotated.csv` |
| 10 | `TimeLag_PreliminaryCorrelations.ipynb` | preliminary lag correlations |
| 11 | `Spatial_Analysis.ipynb` | `Spatial/Zip_Segments.csv`, spatial clusters, maps |
| 12 | `Segment Analysis by Demographics.ipynb` | segment correlations |
| 13 | `Correlation_Analysis.ipynb` | final correlations, `Modeling/Zip_Correlation_Ranking.csv`, report figures |
| 14 | `Predictive_Modeling.ipynb` | `Modeling/Predictive_Features.csv`, `Modeling/Feature_Dictionary.csv` |

Output paths are relative to `data/`.

After step 14, the dashboard in `app/` can be started (see below). It trains its forecasting models from `data/Modeling/Predictive_Features.csv` the first time it runs.

## Running the dashboard

The interactive Streamlit dashboard lives in `app/`. Requires Python 3.12 (3.10+ should work).

1. Open a terminal in the repository root:
   ```
   cd LIHEAP_Project
   ```
2. Install the packages (first time only):
   ```
   pip install -r app/requirements.txt
   ```
3. Start the app:
   ```
   streamlit run app/Home.py
   ```
4. Your browser opens at http://localhost:8501. If it doesn't, paste that address in. Pages are listed in the left sidebar.
5. Stop the app with **Ctrl + C** in the terminal.

The first time you open **Scenario Analysis**, the app trains the CalFresh and food bank models (about a minute) and saves them to `app/models/scenario_models.joblib`; later runs load that file instantly. To retrain by hand, for example after `Predictive_Features.csv` changes, run `python app/train_models.py` or delete the `.joblib` file.

While the app is running, saved code changes appear after clicking **Rerun** in the browser (or pressing **R**).

**Troubleshooting**
- `'streamlit' is not recognized`: Streamlit is not installed in this Python; run step 2 or use `python -m streamlit run app/Home.py`.
- `ModuleNotFoundError: No module named 'scenario'`: start the app from `app/Home.py`, not from a file in `app/pages/`.
- `FileNotFoundError` for a CSV: run the command from the repository root and check that `data/Modeling/Predictive_Features.csv` exists.

**Deploying to Streamlit Community Cloud:** at share.streamlit.io choose **Create app**, select this repository and branch `main`, set the main file path to `app/Home.py`, and set Python 3.12 under Advanced settings. Packages come from `app/requirements.txt`; the first visit after each deploy trains the models.

## Repository layout

- `notebooks/`: the 14 analysis notebooks (run with `notebooks/` as the working directory)
- `app/`: the Streamlit dashboard
  - `Home.py`: entry page (`streamlit run app/Home.py`)
  - `pages/`: one file per dashboard component, e.g. `6_Scenario_Analysis.py`
  - `models/`: trained models, created on first run (`scenario_models.joblib`)
  - `train_models.py`: fits the CalFresh and food bank models from `data/Modeling/Predictive_Features.csv` and saves them to `app/models/scenario_models.joblib`
  - `scenario.py`: scenario engine that loads those models to predict CalFresh dollars and food bank pounds under a changed LIHEAP enrollment
  - `requirements.txt`: packages for Streamlit Community Cloud
- `data/`: the CSV, Excel and GeoJSON datasets the notebooks read and write, grouped by source and stage:
  - `LIHEAP/`, `CalFresh/`, `Food Bank/`: raw and cleaned program data
  - `ACS/`: census demographics by zip code
  - `Integrated/`: coverage matrices and the merged assistance datasets
  - `Policy_TimeLag/`: policy annotations and the lag-annotated LIHEAP data
  - `Spatial/`: zip-code boundaries, spatial clusters and zip segments
  - `Modeling/`: predictive features, feature dictionary and zip correlation ranking
- `figures/`: charts from the analysis notebooks; `figures/maps/` holds the spatial maps
- `reports/`: project deliverables as PDFs
  - `Correlation_StatisticalReport.pdf`: final correlation analysis (lags, policy, demographics, sensitivity)
  - `LIHEAP_DataDictionary.pdf`, `LIHEAP_DataQualityReport.pdf`: LIHEAP data documentation
  - `DataIntegration_QualityAssessment.pdf`: integration of LIHEAP, CalFresh and food bank data
  - `Demographic_Summary_Report.pdf`: census demographics by zip code
  - `Policy_Changes_Inventory.pdf`, `Policy_Impact_Assessment.pdf`, `Policy_Timeline_Visualization.pdf`, `External_Factors_Log.pdf`: policy context
  - `TimeLag_Methodology.pdf`: time-lag approach
  - `Geographic_Disparity_Report.pdf`, `Spatial_Maps_Export.pdf`: spatial analysis and maps

## Setup

`Census_Demographic_Pull.ipynb` needs a free Census API key (https://api.census.gov/data/key_signup.html). Put it in a `.env` file in the repository root:

```
CENSUS_API_KEY=your_key_here
```

`load_dotenv()` finds it from `notebooks/` by searching parent folders. `.env` is git-ignored and must never be committed.

## Data notes

- Record-level LIHEAP pledge data (`data/LIHEAP/LIHEAP_2023_2025.csv`, `LIHEAP_standardized.csv`, `missing_or_invalid_zip.csv`) is not included, so step 1 cannot be rerun from this repository. Its validated zip-level output, `data/LIHEAP/LIHEAP_validated.csv`, is included.
- `data/Spatial/Assistance_Spatial.geojson` (about 550 MB) exceeds GitHub's file-size limit and is regenerated by `Spatial_Analysis.ipynb`.
- Zip-level LIHEAP data is reliable only for January–July 2023; about 74% of later records lack a zip code.

## Changelog

**Commit #10: Streamlit dashboard (`app/`)**
- Created the `app/` folder for the dashboard: `Home.py` (entry page), `pages/6_Scenario_Analysis.py` (component 6), `requirements.txt` and `models/`.
- Moved `scenario.py` and `train_models.py` into `app/`. Their file paths now resolve from the script's own location, so they work from any folder and on Streamlit Community Cloud.
- Fixed bugs in `train_models.py` (`FoodBank_lag1` column name, `feature_names_out` argument) and `scenario.py` (`run_scenario` indentation, sensitivity range now −50% to +100%, "CalFresh dollars" label).
- `scenario.py` now trains the models automatically the first time the app runs, or if the saved models can't be loaded.
- Made the scenario page easier to present:
  - Plain-language labels and a takeaway box that states the result in one sentence.
  - Sensitivity chart on a fixed ±10% axis with a "Your scenario" marker.
  - Zip chart with city names, colors for increases and decreases, and the largest changes at the top.
  - A simpler results table (the CSV download keeps every column) and a "How this works" section.
- Zip codes now show their city, including the 32 PO-box zips (labeled "PO box"), using `data/Spatial/Assistance_Spatial_FUll.csv`.
- Added a "Running the dashboard" section to this README.
- `.gitignore` now excludes trained model files (`app/models/*.joblib`) and Python cache (`__pycache__/`).

**Commit #9: README update**
- Updated the README to reflect the reorganization in Commits #6 to #8, and made a small fix to `scenario.py`.

**Commit #8: Folder reorganization**
- Moved the 14 notebooks into `notebooks/` and grouped `data/` into subfolders by source and pipeline stage (`LIHEAP/`, `CalFresh/`, `Food Bank/`, `ACS/`, `Integrated/`, `Policy_TimeLag/`, `Spatial/`, `Modeling/`).
- Updated every notebook's data and figure paths (`../data/<subfolder>/...`, `../figures/...`).
- Added `scenario.py`, the scenario engine for "what if LIHEAP enrollment changes by X%?" forecasts, and updated the data path in `train_models.py`.

**Commit #7: Model training script**
- Added `train_models.py`, which fits the deployment models (Random Forest for CalFresh, Linear Regression for food bank) from `Predictive_Features.csv` and saves them for the dashboard.

**Commit #6: Data folder**
- Moved all datasets (CSV, Excel, GeoJSON) from the repository root into `data/`.
- Updated every notebook to read and write datasets in `data/` and to save charts in `figures/` (spatial maps in `figures/maps/`).
- Updated the README's pipeline and layout sections.

**Commit #5: Predictive modeling (checkpoint 8)**
- Completed `Predictive_Modeling.ipynb` with the modeling part of the project. Two regression problems predict CalFresh dollars and food bank pounds one month ahead for each zip code.
- Trained three model types (linear regression, random forest, histogram gradient boosting), each with and without the Emergency Allotment policy indicators.
- Tuned and validated with expanding-window time-series cross-validation (train on earlier months, validate on the next). February–June 2023 is used for training and July–August 2023 is held out as the test set.
- Added evaluation against a naive "same as last month" baseline:
  - Metrics by policy regime (Emergency Allotment transition vs post-transition).
  - 90% prediction intervals.
  - Residuals around policy dates.
  - Permutation feature importance, and whether policy indicators improve accuracy.
- Added conclusions for both targets and recommendations for handling future policy changes.

**Commit #4: Feature engineering**
- Added `Predictive_Modeling.ipynb` with the feature-engineering steps:
  - LIHEAP lags (t-1 to t-3).
  - Outcome history.
  - Census demographic indicators.
  - Temporal and year-over-year features.
  - Policy-change indicators.
  - Interaction terms.
  - Consistent missing-value handling.
- Added its outputs: `Predictive_Features.csv` (the modeling dataset) and `Feature_Dictionary.csv` (a description of every feature).

**Commit #2: Project deliverables added to `reports/`**
- Replaced the three Word documents (`DataIntegration_QualityAssessment`, `Demographic_Summary_Report`, `TimeLag_Methodology`) with PDF versions.
- Added eight more deliverables as PDFs: `LIHEAP_DataDictionary`, `LIHEAP_DataQualityReport`, `Policy_Changes_Inventory`, `Policy_Impact_Assessment`, `Policy_Timeline_Visualization`, `External_Factors_Log`, `Geographic_Disparity_Report` and `Spatial_Maps_Export`. These join `Correlation_StatisticalReport`, which was added in Commit #1.
- `reports/` now holds all 12 project deliverables as PDFs that can be viewed directly on GitHub.
- Updated the README's repository layout to list each report.

**Commit #1: Analysis pipeline**
- Added the 13 analysis notebooks, the CSV/GeoJSON data they use, figures (`figures/`, including spatial maps in `figures/maps/`) and the initial reports.
- Added `.gitignore` to exclude secrets (`.env`), oversized files and record-level LIHEAP data.

**Initial commit**
- Created the repository with `README.md` and `.gitattributes`.
