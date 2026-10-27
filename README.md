# Day-ahead wind power forecasting for wind farm nomination

Capstone project: a more accurate day-ahead production forecast for a wind farm, so that its market nomination is closer to real production and the imbalance cost is lower.

## Problem
A wind farm must nominate its hourly production one day ahead. The nomination is based on a weather model's wind forecast, which is often wrong at the turbine location. Small wind errors become large power errors, and every MWh of imbalance costs money.

## Goal
Turn the day-ahead weather forecast into a more accurate hourly power forecast for the whole wind farm, and measure how much of the improvement comes from a better wind forecast.

## Status
- [x] SCADA preprocessing (notebook 01)
- [x] Download of day-ahead NWP forecasts (notebook 02)
- [ ] Hourly aggregation, filters, empirical power curve
- [ ] Wind correction and power forecast models
- [ ] Evaluation: forecast error, imbalance energy and cost

## Data
| Source | Content | Period | Output |
|---|---|---|---|
| [Hill of Towie open dataset v2.1.0](https://doi.org/10.5281/zenodo.22662930) (CC BY 4.0) | 10-min SCADA, 21 Siemens SWT-2.3-VS-82 turbines (48.3 MW), Scotland | Jun 2024 – Apr 2026 | `data/processed/*.parquet` (notebook 01) |
| [Open-Meteo Single Runs API](https://open-meteo.com/en/docs/single-runs-api) (CC BY 4.0) | ECMWF IFS HRES 9 km, runs 00/12 UTC, lead 0–48 h | Apr 2024 – Jun 2026 | `data/nwp/*.csv` (notebook 02) |

Raw SCADA data is not stored in this repository. Download `2024.zip`, `2025.zip`, `2026.zip` and `Hill_of_Towie_turbine_metadata.csv` from [Zenodo](https://zenodo.org/records/22662930) and unzip each year into `data/2024/`, `data/2025/`, `data/2026/`.

## How to run
```bash
pip install -r requirements.txt
```
1. `notebooks/01_scada_preprocessing.ipynb` – selects ~30 SCADA columns and saves turbine- and farm-level Parquet files.
2. `notebooks/02_nwp_open_meteo.ipynb` – downloads every forecast run and saves one CSV file.

## Repository structure
```
├── notebooks/
├── data/                   # mostly not tracked by git
│   ├── 2024/ 2025/ 2026/   # raw SCADA from Zenodo
│   ├── processed/          # Parquet files (notebook 01)
│   └── nwp/                # NWP forecasts (notebook 02)
├── requirements.txt
└── README.md
```

## Results
<!-- TODO: add after model evaluation -->

## Citation
- Clerc, A., & Lingkan, E. (2026). *Hill of Towie wind farm open dataset* (v2.1.0). Zenodo. https://doi.org/10.5281/zenodo.22662930
- Weather data by [Open-Meteo.com](https://open-meteo.com/). Zippenfenig, P. (2023). *Open-Meteo.com Weather API*. Zenodo. https://doi.org/10.5281/ZENODO.7970649

## Author
Aleksandar Zecevic – [@A3eko](https://github.com/A3eko)