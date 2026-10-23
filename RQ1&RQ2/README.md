# RQ1 & RQ2

This folder contains the data and scripts used to answer the first two research questions of the study:

- **RQ1:** To what extent can alternative compression formats reduce the size of npm packages?
- **RQ2:** How much network-transfer energy could be saved by replacing the current npm package compression format with alternative compression algorithms?

The analysis considers four alternatives to the current gzip-based npm package format: **Brotli, XZ, Zopfli, and Zstandard**.

## Structure

```text
RQ1&RQ2/
├── data/
│   ├── brotli_grid_search/
│   ├── xz_grid_search/
│   ├── zopfli_grid_search/
│   ├── zstd_grid_search/
│   ├── package_size_comparison.csv
│   ├── package_size_comparison_2500.csv
│   ├── top_2500_depended.csv
│   └── top_2500_depended_enriched.csv
│
├── scripts/
│   ├── analyze_results.py
│   ├── brotli_grid_search.py
│   ├── collect_downloads.py
│   ├── compare_grid_search.py
│   ├── compare_sizes.py
│   ├── compute_energy_savings.py
│   ├── download_sample.py
│   ├── plots.py
│   ├── repack_with_brotli.py
│   ├── repack_with_xz.py
│   ├── repack_with_zopfli.py
│   ├── repack_with_zstd.py
│   ├── unpack_npm_tarballs.py
│   ├── xz_grid_search.py
│   ├── zopfli_grid_search.py
│   └── zstd_grid_search.py
│
└── OpenSourceInsightsQuery.txt
```

## Data

`top_2500_depended.csv` contains the 2,500 npm packages selected according to the number of dependent packages.

`top_2500_depended_enriched.csv` enriches this dataset with additional information used in the analysis, including npm download data.

`package_size_comparison_2500.csv` contain the package-size measurements used to compare the original npm archives with the alternative compression formats.

The `*_grid_search/` directories contain the results produced while evaluating different configurations of Brotli, XZ, Zopfli, and Zstandard.

`OpenSourceInsightsQuery.txt` contains the query used to retrieve the initial package dataset from Open Source Insights.

## Scripts

The scripts implement the main stages of the RQ1 and RQ2 analysis:

- `download_sample.py` — downloads the selected npm packages.
- `collect_downloads.py` — collects npm download statistics.
- `unpack_npm_tarballs.py` — extracts the original npm archives.
- `repack_with_*.py` — recompresses packages using the evaluated formats.
- `*_grid_search.py` — evaluates the available compression configurations for each tool.
- `compare_grid_search.py` — compares the grid-search results.
- `compare_sizes.py` — compares archive sizes across compression formats.
- `compute_energy_savings.py` — computes the estimated network-transfer energy savings from package-size reductions and download volumes.
- `analyze_results.py` — performs the final analysis of the collected results.
- `plots.py` — generates the plots used in the analysis.

## Analysis Workflow

The analysis follows four main steps:

1. Select the 2,500 npm packages with the largest number of dependents and collect their download statistics.
2. Download the original npm archives and recompress them using Brotli, XZ, Zopfli, and Zstandard.
3. Perform a grid search over the supported compression configurations and compare the resulting archive sizes.
4. Combine package-size reductions with npm download volumes to estimate potential network-transfer energy savings.

Requirements

The analysis requires Python 3 and the command-line implementations of the evaluated compression tools:

Brotli 1.2.0

XZ / XZ Utils 5.4.6

Zopfli 1.0.3

Zstandard (zstd) 1.5.5

The corresponding executables must be available in the system PATH before running the compression and grid-search scripts.

Additional Python dependencies required by the analysis scripts should be installed in the execution environment.