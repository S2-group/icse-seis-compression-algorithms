# Can Data Compression Save Energy End-to-End? The Case of npm Packages

This repository contains the replication package and dataset of the paper 'Can Data Compression Save Energy End-to-End? The Case of npm Packages'

## How to cite the dataset

If this replication package is helping your research, consider to cite it is as follows, thanks!

```
@inproceedings{energycompression2026,
  url = { <PREPRINT_URL> },
  numpages = { <N> },
  pages = { To appear },
  year = { 2026 },
}
```

## Overview of the replication package

The replication package contains one folder for each research question of the paper. The structure is as follows:

- `./RQ1&RQ2`: Contains the material/code/data for RQ1 and RQ2. See [RQ1](#rq1) and [RQ2](#rq2) below.
- `./RQ3`: Contains the package sampling, the experiment configuration and scripts, the raw measurements, and the data analysis for RQ3 (energy consumption of decompressing npm packages compressed with different algorithms). See [RQ3](#rq3) below.

## RQ1

## RQ2

## RQ3

RQ3 compares the energy consumed when decompressing npm packages that were compressed with different algorithms. The baseline is the `npm` format (gzip-compressed `.tgz`), which is compared against `xz`, `brotli`, `zstd` and `zopfli`.

The experiment uses **63 sampled npm packages × 5 algorithms = 315 runs**, each repeated **30 times** (9450 measurements in total). Energy is measured with `perf stat` (`power/energy-pkg/` and `power/energy-ram/`), and the experiment is orchestrated with [Experiment-Runner](https://github.com/s2-group/experiment-runner).

## Running the entire replication package

To run the replication package, please follow the instructions in each folder.

## License

<LICENSE – to be added>
