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

After step 14, run `python train_models.py` from the repository root to fit the two deployment models. `scenario.py` loads them for "what if LIHEAP enrollment changes by X%?" scenarios.

## Repository layout

- `notebooks/`: the 14 analysis notebooks (run with `notebooks/` as the working directory)
- `train_models.py`: fits the CalFresh and food bank models from `data/Modeling/Predictive_Features.csv` and saves them to `models/scenario_models.joblib` (created on first run)
- `scenario.py`: scenario engine that loads those models to predict CalFresh dollars and food bank pounds under a changed LIHEAP enrollment
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

**Folder reorganization**
- Moved the notebooks into `notebooks/` and grouped `data/` into subfolders by source and pipeline stage.
- Updated every notebook's data and figure paths (`../data/<subfolder>/...`, `../figures/...`) and the data paths in `train_models.py` and `scenario.py`.
- Added `Predictive_Modeling.ipynb` to the pipeline table and documented `train_models.py` and `scenario.py` in the repository layout.

**Data folder**
- Moved all datasets (CSV, Excel, GeoJSON) from the repository root into `data/`.
- Updated every notebook to read and write datasets in `data/` and to save charts in `figures/` (spatial maps in `figures/maps/`).

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
