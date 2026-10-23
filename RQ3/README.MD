# Structure of `./RQ3`

```
RQ3
├── pkgs/       # Package sampling and compressed-size computation
├── server/     # Scripts to set up and profile the experiment machine
├── results/    # Raw measurements of the experiment
└── data/       # Analysis notebook and datasets
```

## `./RQ3/pkgs`

Sampling of the packages used in the experiment. Since package size varies a lot (from ~360 bytes to ~45 MB), size is used as a blocking factor rather than comparing packages of different sizes directly.

- `pkgs-buckets.ipynb`: Checks that the directories of each algorithm contain the same packages, collapses platform-specific "family" duplicates, defines the size buckets and draws the sample of 63 packages.
- `gen_sizes.py`: Collects the size of every compressed package file of a given algorithm and writes it to a CSV file.
  Usage: `python gen_sizes.py <algorithm> <output-dir>` (e.g., `python gen_sizes.py zstd samples`). The script expects a folder named after the algorithm (`npm`, `xz`, `brotli`, `zstd` or `zopfli`) in the current directory containing the packages with the expected extension (`.tgz`, `.tar.xz`, `.tar.br`, `.tar.zst`, `.tgz`, respectively).
- `samples/`: The sampled packages and their compressed sizes, one CSV file per algorithm (`npm.csv`, `xz.csv`, `brotli.csv`, `zstd.csv`, `zopfli.csv`). `npm.csv` also includes the package family, the log-size and the size bucket.

## `./RQ3/server`

Scripts to be run on the machine where the experiment is executed.

- `install-compression-tools.sh`: Installs and verifies the command-line tools needed to decompress the packages: `gzip`, `xz`, `zstd`, `brotli` and `zopfli`.
  Usage: `bash install-compression-tools.sh`
- `profile.sh`: Wrapper that runs a decompression command under `perf stat` and stores the energy readings (package and RAM, in Joules) and the elapsed time in `stat.txt`, together with the executed command. It must be executed as root.
  Usage: `./profile.sh <run-output-dir> <command> [args...] <output-dir>`

## `./RQ3/results`

- `npm-exp/`: Raw output of the experiment.
  - `run_table.csv`: Table with one row per run and repetition (energy, execution time, algorithm and package).
  - `metadata.json`: Metadata of the Experiment-Runner execution.
  - `run_<N>_repetition_<M>/`: One folder per measurement (`N` = 0–314 identifies the package/algorithm combination, `M` = 0–29 the repetition), each containing the `stat.txt` produced by `perf stat`.

## `./RQ3/data`

- `RQ3.ipynb`: The data analysis of RQ3. It merges the measurements with the compressed sizes, computes the total energy (package + RAM, converted from J to mWh).
- `top_2500_depended_enriched.csv`: The 2500 most depended-upon npm packages, enriched with registry metadata (downloads over the last week/month/year, latest version, tarball URL, license, etc.). It is used to weight the results by download counts.
- `weighted_data.csv`: Measurements merged with the download counts, including the projected decompression energy over a week, a month and a year (`energy-week`, `energy-month`, `energy-year`).

## Replicating the data analysis

1. Install the Python dependencies: `pip install pandas numpy scipy matplotlib seaborn scikit-posthocs jupyter`
2. Open `RQ3/data/RQ3.ipynb` from within the `RQ3/data` folder (the notebook uses relative paths such as `../pkgs/samples` and `../results/npm-exp/run_table.csv`).
3. Run all the cells.

## Replicating the experiment

1. Set up an Ubuntu/Debian machine with `perf` and access to the RAPL energy counters (`power/energy-pkg/` and `power/energy-ram/`).
2. Install the compression tools: `bash RQ3/server/install-compression-tools.sh`
3. Prepare the compressed packages for the 63 sampled packages listed in `RQ3/pkgs/samples` (one folder per algorithm), and compute their sizes with `RQ3/pkgs/gen_sizes.py` if needed.
4. Run the experiment with [Experiment-Runner](https://github.com/s2-group/experiment-runner), which calls `RQ3/server/profile.sh` for each run (30 repetitions per package and algorithm).
5. Run the data analysis as described above.

# Requirements

- Ubuntu/Debian machine with `perf` and RAPL energy counters (for the experiment)
- `gzip`, `xz-utils`, `zstd`, `brotli`, `zopfli` (installed by `RQ3/server/install-compression-tools.sh`)
- Python 3 with `pandas`, `numpy`, `scipy`, `matplotlib`, `seaborn`, `scikit-posthocs` and Jupyter (for the analysis)
- [Experiment-Runner](https://github.com/s2-group/experiment-runner)