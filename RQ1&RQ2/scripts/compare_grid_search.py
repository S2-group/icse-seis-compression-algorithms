#!/usr/bin/env python3

import argparse
import re
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd


DEFAULT_XZ_DIR = "../data/xz_grid_search"
DEFAULT_ZSTD_DIR = "../data/zstd_grid_search"
DEFAULT_ZOPFLI_DIR = "../data/zopfli_grid_search"
DEFAULT_BROTLI_DIR = "../data/brotli_grid_search"
DEFAULT_SIZE_CSV = "../data/package_size_comparison_2500.csv"
DEFAULT_OUTPUT_DIR = "../data/grid_search_summary"


ALGORITHMS = ["xz", "zstd", "zopfli", "brotli"]


NUMERIC_SUMMARY_COLUMNS = [
    "CompressedBytes",
    "CompressedMB",
    "ElapsedMilliseconds",
    "UnpackedBytes",
    "OriginalBytes",
    "OriginalMB",
    "SavingVsOriginalPercent",
    "GainBytesVsOriginal",
    "LargerPackagesWithoutSizeGain",
]


def safe_read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, keep_default_na=False)


def parse_bool(value) -> bool:
    raw = str(value).strip().lower()
    return raw in {"true", "1", "yes", "y"}


def parse_xz_config(path: Path, df: pd.DataFrame) -> tuple[int, bool, str]:
    level = None
    extreme = False

    if "Level" in df.columns and len(df) > 0:
        values = pd.to_numeric(df["Level"], errors="coerce").dropna()
        if not values.empty:
            level = int(values.iloc[0])

    if "Extreme" in df.columns and len(df) > 0:
        extreme = parse_bool(df["Extreme"].iloc[0])

    if level is None:
        match = re.search(r"xz_l(\d+)(_extreme)?", path.stem)
        if match:
            level = int(match.group(1))
            extreme = match.group(2) is not None

    if level is None:
        raise ValueError(f"Cannot parse xz level from {path}")

    config_label = f"l{level}-extreme" if extreme else f"l{level}"

    return level, extreme, config_label


def parse_zstd_config(path: Path, df: pd.DataFrame) -> tuple[int, bool, str]:
    level = None
    ultra = False

    if "Level" in df.columns and len(df) > 0:
        values = pd.to_numeric(df["Level"], errors="coerce").dropna()
        if not values.empty:
            level = int(values.iloc[0])

    if "Ultra" in df.columns and len(df) > 0:
        ultra = parse_bool(df["Ultra"].iloc[0])

    if level is None:
        match = re.search(r"zstd_l(\d+)(_ultra)?", path.stem)
        if match:
            level = int(match.group(1))
            ultra = match.group(2) is not None

    if level is None:
        raise ValueError(f"Cannot parse zstd level from {path}")

    config_label = f"l{level}-ultra" if ultra else f"l{level}"

    return level, ultra, config_label


def parse_zopfli_config(path: Path, df: pd.DataFrame) -> tuple[int, str]:
    iterations = None

    if "Iterations" in df.columns and len(df) > 0:
        values = pd.to_numeric(df["Iterations"], errors="coerce").dropna()
        if not values.empty:
            iterations = int(values.iloc[0])

    if iterations is None:
        match = re.search(r"zopfli_i(\d+)", path.stem)
        if match:
            iterations = int(match.group(1))

    if iterations is None:
        raise ValueError(f"Cannot parse zopfli iterations from {path}")

    config_label = f"i{iterations}"

    return iterations, config_label


def parse_brotli_config(path: Path, df: pd.DataFrame) -> tuple[int, Optional[int], str]:
    quality = None
    lgwin = None

    if "Quality" in df.columns and len(df) > 0:
        values = pd.to_numeric(df["Quality"], errors="coerce").dropna()
        if not values.empty:
            quality = int(values.iloc[0])

    if "Lgwin" in df.columns and len(df) > 0:
        values = pd.to_numeric(df["Lgwin"], errors="coerce").dropna()
        if not values.empty:
            lgwin = int(values.iloc[0])

    if quality is None:
        match = re.search(r"brotli_q(\d+)_lgwin(\d+|default)", path.stem)
        if match:
            quality = int(match.group(1))
            if match.group(2) == "default":
                lgwin = None
            else:
                lgwin = int(match.group(2))

    if quality is None:
        raise ValueError(f"Cannot parse brotli quality from {path}")

    if lgwin is None:
        config_label = f"q{quality}-default"
    else:
        config_label = f"q{quality}-w{lgwin}"

    return quality, lgwin, config_label


def normalize_algorithm_csv(path: Path, algorithm: str) -> pd.DataFrame:
    df = safe_read_csv(path)

    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["SourceCSV"] = str(path)
    df["Algorithm"] = algorithm

    if algorithm == "xz":
        parameter, is_special, config_label = parse_xz_config(path, df)
        size_column = "XzBytes"
        mb_column = "XzMB"

        df["Parameter"] = parameter
        df["ParameterName"] = "level"
        df["SpecialMode"] = "extreme" if is_special else "standard"
        df["ConfigLabel"] = config_label

    elif algorithm == "zstd":
        parameter, is_special, config_label = parse_zstd_config(path, df)
        size_column = "ZstdBytes"
        mb_column = "ZstdMB"

        df["Parameter"] = parameter
        df["ParameterName"] = "level"
        df["SpecialMode"] = "ultra" if is_special else "standard"
        df["ConfigLabel"] = config_label

    elif algorithm == "zopfli":
        parameter, config_label = parse_zopfli_config(path, df)
        size_column = "ZopfliBytes"
        mb_column = "ZopfliMB"

        df["Parameter"] = parameter
        df["ParameterName"] = "iterations"
        df["SpecialMode"] = "standard"
        df["ConfigLabel"] = config_label

    elif algorithm == "brotli":
        parameter, lgwin, config_label = parse_brotli_config(path, df)
        size_column = "BrotliBytes"
        mb_column = "BrotliMB"

        df["Parameter"] = parameter
        df["ParameterName"] = "quality"
        df["SpecialMode"] = f"lgwin{lgwin}" if lgwin is not None else "lgwin_default"
        df["ConfigLabel"] = config_label

        if "Lgwin" not in df.columns:
            df["Lgwin"] = lgwin if lgwin is not None else ""

    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")

    if "PackageKey" not in df.columns:
        raise ValueError(f"Missing PackageKey in {path}")

    if size_column not in df.columns:
        raise ValueError(f"Missing {size_column} in {path}")

    df["PackageKey"] = df["PackageKey"].astype(str).str.strip()
    df["CompressedBytes"] = pd.to_numeric(df[size_column], errors="coerce")

    if mb_column in df.columns:
        df["CompressedMB"] = pd.to_numeric(df[mb_column], errors="coerce")
    else:
        df["CompressedMB"] = df["CompressedBytes"] / (1024 * 1024)

    if "ElapsedMilliseconds" in df.columns:
        df["ElapsedMilliseconds"] = pd.to_numeric(
            df["ElapsedMilliseconds"],
            errors="coerce",
        )
    else:
        df["ElapsedMilliseconds"] = pd.NA

    if "UnpackedBytes" in df.columns:
        df["UnpackedBytes"] = pd.to_numeric(df["UnpackedBytes"], errors="coerce")
    else:
        df["UnpackedBytes"] = pd.NA

    if "Status" not in df.columns:
        df["Status"] = "unknown"

    return df


def load_grid_search_results(directory: Path, algorithm: str) -> pd.DataFrame:
    if not directory.exists():
        print(f"WARNING: directory does not exist: {directory}")
        return pd.DataFrame()

    files = sorted(directory.glob("*_results.csv"))

    if not files:
        print(f"WARNING: no *_results.csv files found in: {directory}")
        return pd.DataFrame()

    frames = []

    for path in files:
        try:
            frame = normalize_algorithm_csv(path, algorithm)
            if not frame.empty:
                frames.append(frame)
        except Exception as exc:
            print(f"WARNING: skipping {path}: {exc}")

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


def load_original_sizes(size_csv: Optional[Path]) -> pd.DataFrame:
    if size_csv is None:
        return pd.DataFrame()

    if not size_csv.exists():
        print(f"WARNING: size CSV does not exist: {size_csv}")
        return pd.DataFrame()

    df = safe_read_csv(size_csv)

    if "PackageKey" not in df.columns or "OriginalBytes" not in df.columns:
        print(
            f"WARNING: size CSV must contain PackageKey and OriginalBytes: {size_csv}"
        )
        return pd.DataFrame()

    df = df[["PackageKey", "OriginalBytes"]].copy()
    df["PackageKey"] = df["PackageKey"].astype(str).str.strip()
    df["OriginalBytes"] = pd.to_numeric(df["OriginalBytes"], errors="coerce")
    df["OriginalMB"] = df["OriginalBytes"] / (1024 * 1024)

    df = df.dropna(subset=["OriginalBytes"])
    df = df.drop_duplicates(subset=["PackageKey"], keep="first")

    return df


def add_original_size_and_gain(
    grid_df: pd.DataFrame,
    original_sizes: pd.DataFrame,
) -> pd.DataFrame:
    df = grid_df.copy()

    if original_sizes.empty:
        df["OriginalBytes"] = pd.NA
        df["OriginalMB"] = pd.NA
        df["GainBytesVsOriginal"] = pd.NA
        df["HasSizeGainVsOriginal"] = pd.NA
        df["SavingVsOriginalPercent"] = pd.NA
        return df

    df = df.merge(
        original_sizes,
        on="PackageKey",
        how="left",
        validate="many_to_one",
    )

    df["GainBytesVsOriginal"] = df["OriginalBytes"] - df["CompressedBytes"]
    df["HasSizeGainVsOriginal"] = df["GainBytesVsOriginal"] > 0

    df["SavingVsOriginalPercent"] = pd.NA
    valid = (
        df["OriginalBytes"].notna()
        & df["CompressedBytes"].notna()
        & (df["OriginalBytes"] > 0)
    )

    df.loc[valid, "SavingVsOriginalPercent"] = (
        1 - (df.loc[valid, "CompressedBytes"] / df.loc[valid, "OriginalBytes"])
    ) * 100

    return df


def add_larger_no_gain_analysis(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["LargerPackagesWithoutSizeGain"] = pd.NA
    df["NoLargerPackageWithoutSizeGain"] = pd.NA

    required = [
        "Algorithm",
        "ConfigLabel",
        "OriginalBytes",
        "HasSizeGainVsOriginal",
    ]

    for column in required:
        if column not in df.columns:
            return df

    valid_mask = (
        (df["Status"] == "success")
        & df["OriginalBytes"].notna()
        & df["HasSizeGainVsOriginal"].notna()
    )

    group_cols = [
        "Algorithm",
        "SpecialMode",
        "ConfigLabel",
    ]

    for _, group in df[valid_mask].groupby(group_cols, dropna=False):
        group = group.copy()
        group["OriginalBytes"] = pd.to_numeric(group["OriginalBytes"], errors="coerce")
        group = group.dropna(subset=["OriginalBytes"])

        if group.empty:
            continue

        no_gain_sizes = group.loc[
            ~group["HasSizeGainVsOriginal"].astype(bool),
            "OriginalBytes",
        ].sort_values().tolist()

        if not no_gain_sizes:
            df.loc[group.index, "LargerPackagesWithoutSizeGain"] = 0
            df.loc[group.index, "NoLargerPackageWithoutSizeGain"] = True
            continue

        no_gain_sizes_series = pd.Series(no_gain_sizes)

        for index, row in group.iterrows():
            original_size = row["OriginalBytes"]
            count_larger_no_gain = int((no_gain_sizes_series > original_size).sum())

            df.at[index, "LargerPackagesWithoutSizeGain"] = count_larger_no_gain
            df.at[index, "NoLargerPackageWithoutSizeGain"] = count_larger_no_gain == 0

    df["LargerPackagesWithoutSizeGain"] = pd.to_numeric(
        df["LargerPackagesWithoutSizeGain"],
        errors="coerce",
    )

    return df


def smallest_original_mb_with_no_larger_no_gain(group: pd.DataFrame):
    if "NoLargerPackageWithoutSizeGain" not in group.columns:
        return pd.NA

    valid = group[
        (group["NoLargerPackageWithoutSizeGain"] == True)
        & group["OriginalMB"].notna()
    ].copy()

    if valid.empty:
        return pd.NA

    return valid["OriginalMB"].min()


def add_parameter_ordinal(summary: pd.DataFrame) -> pd.DataFrame:
    summary = summary.copy()
    summary["ParameterOrdinal"] = pd.NA

    for algorithm, algorithm_df in summary.groupby("Algorithm", dropna=False):
        configs = (
            algorithm_df[
                [
                    "Parameter",
                    "SpecialMode",
                    "ConfigLabel",
                ]
            ]
            .drop_duplicates()
            .sort_values(
                by=["SpecialMode", "Parameter"],
                ascending=[True, True],
            )
            .reset_index(drop=True)
        )

        ordinal_map = {}

        for idx, row in configs.iterrows():
            key = (
                row["Parameter"],
                row["SpecialMode"],
                row["ConfigLabel"],
            )
            ordinal_map[key] = idx + 1

        mask = summary["Algorithm"] == algorithm

        for index, row in summary[mask].iterrows():
            key = (
                row["Parameter"],
                row["SpecialMode"],
                row["ConfigLabel"],
            )
            summary.at[index, "ParameterOrdinal"] = ordinal_map[key]

    summary["ParameterOrdinal"] = pd.to_numeric(
        summary["ParameterOrdinal"],
        errors="coerce",
    )

    return summary


def summarize_group(df: pd.DataFrame) -> pd.DataFrame:
    success = df[df["Status"] == "success"].copy()

    if success.empty:
        return pd.DataFrame()

    group_cols = [
        "Algorithm",
        "ParameterName",
        "Parameter",
        "SpecialMode",
        "ConfigLabel",
    ]

    rows = []

    for keys, group in success.groupby(group_cols, dropna=False):
        algorithm, parameter_name, parameter, special_mode, config_label = keys

        has_gain = group["HasSizeGainVsOriginal"].fillna(False)

        total_original_bytes = group["OriginalBytes"].sum()
        total_compressed_bytes = group["CompressedBytes"].sum()
        total_gain_bytes = total_original_bytes - total_compressed_bytes

        row = {
                "Algorithm": algorithm,
                "ParameterName": parameter_name,
                "Parameter": parameter,
                "SpecialMode": special_mode,
                "ConfigLabel": config_label,
                "NPackages": len(group),
                "NSizeGainVsOriginal": int(has_gain.sum()),

                # Compressed archive size, package-level descriptive statistics
                "MedianCompressedBytes": group["CompressedBytes"].median(),
                "MedianCompressedMB": group["CompressedMB"].median(),
                "Q3CompressedMB": group["CompressedMB"].quantile(0.75),
                "MeanCompressedMB": group["CompressedMB"].mean(),

                # Total compressed dataset size for this configuration
                "TotalCompressedBytes": group["CompressedBytes"].sum(),
                "TotalCompressedMB": group["CompressedBytes"].sum() / (1024 * 1024),

                # Baseline/original archive size
                "MeanOriginalMB": group["OriginalMB"].mean(),
                "MedianOriginalMB": group["OriginalMB"].median(),
                "Q3OriginalMB": group["OriginalMB"].quantile(0.75),
                "TotalOriginalBytes": group["OriginalBytes"].sum(),
                "TotalOriginalMB": group["OriginalBytes"].sum() / (1024 * 1024),

                # Compression time
                "MedianElapsedMilliseconds": group["ElapsedMilliseconds"].median(),
                "MeanElapsedMilliseconds": group["ElapsedMilliseconds"].mean(),
                "Q3ElapsedMilliseconds": group["ElapsedMilliseconds"].quantile(0.75),
                "TotalElapsedMilliseconds": group["ElapsedMilliseconds"].sum(),

                # Package-level percentage savings
                "MedianSavingVsOriginalPercent": pd.to_numeric(
                    group["SavingVsOriginalPercent"],
                    errors="coerce",
                ).median(),
                "Q3SavingVsOriginalPercent": pd.to_numeric(
                    group["SavingVsOriginalPercent"],
                    errors="coerce",
                ).quantile(0.75),
                "MeanSavingVsOriginalPercent": pd.to_numeric(
                    group["SavingVsOriginalPercent"],
                    errors="coerce",
                ).mean(),

                # Absolute gain with respect to original archives
                "MedianGainBytesVsOriginal": group["GainBytesVsOriginal"].median(),
                "Q3GainBytesVsOriginal": group["GainBytesVsOriginal"].quantile(0.75),
                "MeanGainBytesVsOriginal": group["GainBytesVsOriginal"].mean(),
                "TotalGainBytesVsOriginal": group["GainBytesVsOriginal"].sum(),
                "TotalGainMBVsOriginal": group["GainBytesVsOriginal"].sum() / (1024 * 1024),

                # Dataset-level percentage saving
                "TotalSavingVsOriginalPercent": (total_gain_bytes / total_original_bytes) * 100,

                "SmallestOriginalMBWithNoLargerNoGain": smallest_original_mb_with_no_larger_no_gain(group),
            }

        rows.append(row)

    summary = pd.DataFrame(rows)

    if summary.empty:
        return summary

    summary = summary.sort_values(
        by=["Algorithm", "SpecialMode", "Parameter"],
        ascending=[True, True, True],
    )

    summary = add_parameter_ordinal(summary)

    return summary


def descriptive_stats_by_config(df: pd.DataFrame) -> pd.DataFrame:
    success = df[df["Status"] == "success"].copy()

    if success.empty:
        return pd.DataFrame()

    rows = []
    group_cols = [
        "Algorithm",
        "ParameterName",
        "Parameter",
        "SpecialMode",
        "ConfigLabel",
    ]

    for keys, group in success.groupby(group_cols, dropna=False):
        algorithm, parameter_name, parameter, special_mode, config_label = keys

        for column in NUMERIC_SUMMARY_COLUMNS:
            if column not in group.columns:
                continue

            series = pd.to_numeric(group[column], errors="coerce").dropna()

            if series.empty:
                continue

            q1 = series.quantile(0.25)
            median = series.quantile(0.50)
            q3 = series.quantile(0.75)

            rows.append(
                {
                    "Algorithm": algorithm,
                    "ParameterName": parameter_name,
                    "Parameter": parameter,
                    "SpecialMode": special_mode,
                    "ConfigLabel": config_label,
                    "Column": column,
                    "Count": int(series.count()),
                    "Min": series.min(),
                    "Q1": q1,
                    "Median": median,
                    "Q3": q3,
                    "Max": series.max(),
                    "Mean": series.mean(),
                    "StdDev": series.std(),
                    "IQR": q3 - q1,
                }
            )

    result = pd.DataFrame(rows)

    if result.empty:
        return result

    return result.sort_values(
        by=["Algorithm", "SpecialMode", "Parameter", "Column"],
        ascending=[True, True, True, True],
    )


def print_descriptive_stats(stats: pd.DataFrame) -> None:
    if stats.empty:
        print("No descriptive statistics available.")
        return

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 220)
    pd.set_option("display.float_format", "{:,.4f}".format)

    for algorithm in stats["Algorithm"].drop_duplicates():
        print(f"\nDescriptive statistics - {algorithm}")
        print("=" * 120)

        alg_stats = stats[stats["Algorithm"] == algorithm]

        for config_label in alg_stats["ConfigLabel"].drop_duplicates():
            print(f"\nConfig: {config_label}")
            print("-" * 120)

            subset = alg_stats[alg_stats["ConfigLabel"] == config_label]
            print(
                subset[
                    [
                        "Column",
                        "Count",
                        "Min",
                        "Q1",
                        "Median",
                        "Q3",
                        "Max",
                        "Mean",
                        "StdDev",
                        "IQR",
                    ]
                ].to_string(index=False)
            )


def summary_for_print(summary: pd.DataFrame) -> pd.DataFrame:
    summary_print_columns = [
        "Algorithm",
        "Parameter",
        "ConfigLabel",

        "MedianCompressedMB",
        "Q3CompressedMB",
        "MeanCompressedMB",
        "TotalCompressedMB",

        "MedianOriginalMB",
        "Q3OriginalMB",
        "MeanOriginalMB",
        "TotalOriginalMB",

        "TotalGainMBVsOriginal",
        "TotalSavingVsOriginalPercent",

        "MedianElapsedMilliseconds",
        "MeanElapsedMilliseconds",
        "Q3ElapsedMilliseconds",
        "TotalElapsedMilliseconds",

        "NSizeGainVsOriginal",
        "MedianSavingVsOriginalPercent",
        "Q3SavingVsOriginalPercent",
        "MeanSavingVsOriginalPercent",

        "SmallestOriginalMBWithNoLargerNoGain",
    ]

    if summary.empty:
        return summary

    available_columns = [
        column for column in summary_print_columns if column in summary.columns
    ]

    return summary[available_columns].copy()


def plot_metric_for_algorithm(
    summary: pd.DataFrame,
    algorithm: str,
    y_column: str,
    ylabel: str,
    title: str,
    output_path: Path,
) -> None:
    subset = summary[summary["Algorithm"] == algorithm].copy()

    if subset.empty:
        print(f"WARNING: no summary rows for {algorithm}; skipping plot {output_path}")
        return

    subset = subset.dropna(subset=[y_column, "ParameterOrdinal"]).copy()

    if subset.empty:
        print(f"WARNING: no values for {algorithm}:{y_column}; skipping {output_path}")
        return

    subset = subset.sort_values(
        by=["ParameterOrdinal"],
        ascending=[True],
    )

    plt.figure(figsize=(10, 6))

    for special_mode, group in subset.groupby("SpecialMode", dropna=False):
        group = group.sort_values("ParameterOrdinal")
        label = str(special_mode)

        plt.plot(
            group["ParameterOrdinal"],
            group[y_column],
            marker="o",
            label=label,
        )

        for _, row in group.iterrows():
            plt.annotate(
                str(row["ConfigLabel"]),
                (row["ParameterOrdinal"], row[y_column]),
                textcoords="offset points",
                xytext=(0, 6),
                ha="center",
                fontsize=8,
            )

    plt.xlabel("Ordinal grid-search parameter")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, alpha=0.3)

    x_ticks = sorted(subset["ParameterOrdinal"].dropna().unique())
    plt.xticks(x_ticks)

    if subset["SpecialMode"].nunique() > 1:
        plt.legend(title="Mode")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def create_plots(summary: pd.DataFrame, output_dir: Path) -> None:
    if summary.empty:
        print("No summary available; skipping plots.")
        return

    plot_specs = [
        (
            "MedianCompressedMB",
            "Median compressed size (MB)",
            "median_size_over_parameter",
        ),
        (
            "MedianElapsedMilliseconds",
            "Median compression time (ms)",
            "median_compression_time_over_parameter",
        ),
        (
            "NSizeGainVsOriginal",
            "Number of packages with size gain vs original",
            "num_packages_with_size_gain_over_parameter",
        ),
        (
            "SmallestOriginalMBWithNoLargerNoGain",
            "Smallest original MB with no larger no-gain package",
            "smallest_original_mb_with_no_larger_no_gain_over_parameter",
        ),
    ]

    for algorithm in ALGORITHMS:
        for y_column, ylabel, filename_stem in plot_specs:
            output_path = output_dir / f"{algorithm}_{filename_stem}.png"
            title = f"{algorithm}: {ylabel}"
            plot_metric_for_algorithm(
                summary=summary,
                algorithm=algorithm,
                y_column=y_column,
                ylabel=ylabel,
                title=title,
                output_path=output_path,
            )


def plot_combined_metric(
    summary: pd.DataFrame,
    y_column: str,
    ylabel: str,
    title: str,
    output_path: Path,
) -> None:
    subset = summary.copy()

    if subset.empty:
        print(f"WARNING: no summary rows; skipping combined plot {output_path}")
        return

    subset = subset.dropna(subset=[y_column, "ParameterOrdinal"]).copy()

    if subset.empty:
        print(f"WARNING: no values for {y_column}; skipping combined plot {output_path}")
        return

    plt.figure(figsize=(12, 7))

    for algorithm, group in subset.groupby("Algorithm", dropna=False):
        group = group.sort_values("ParameterOrdinal")

        plt.plot(
            group["ParameterOrdinal"],
            group[y_column],
            marker="o",
            label=str(algorithm),
        )

        for _, row in group.iterrows():
            plt.annotate(
                str(row["ConfigLabel"]),
                (row["ParameterOrdinal"], row[y_column]),
                textcoords="offset points",
                xytext=(0, 6),
                ha="center",
                fontsize=8,
            )

    max_ordinal = int(subset["ParameterOrdinal"].max())
    plt.xticks(range(1, max_ordinal + 1))

    plt.xlabel("Ordinal grid-search parameter within each algorithm")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, alpha=0.3)
    plt.legend(title="Algorithm")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def create_combined_plots(summary: pd.DataFrame, output_dir: Path) -> None:
    if summary.empty:
        print("No summary available; skipping combined plots.")
        return

    plot_specs = [
        (
            "MedianCompressedMB",
            "Median compressed size (MB)",
            "combined_median_size_over_ordinal_parameter",
        ),
        (
            "MedianElapsedMilliseconds",
            "Median compression time (ms)",
            "combined_median_compression_time_over_ordinal_parameter",
        ),
        (
            "NSizeGainVsOriginal",
            "Number of packages with size gain vs original",
            "combined_num_packages_with_size_gain_over_ordinal_parameter",
        ),
        (
            "SmallestOriginalMBWithNoLargerNoGain",
            "Smallest original MB with no larger no-gain package",
            "combined_smallest_original_mb_with_no_larger_no_gain_over_ordinal_parameter",
        ),
    ]

    for y_column, ylabel, filename_stem in plot_specs:
        output_path = output_dir / f"{filename_stem}.png"
        title = f"All algorithms: {ylabel}"
        plot_combined_metric(
            summary=summary,
            y_column=y_column,
            ylabel=ylabel,
            title=title,
            output_path=output_path,
        )

def print_baseline_summary(original_sizes: pd.DataFrame) -> None:
    if original_sizes.empty:
        print("No baseline/original size summary available.")
        return

    series_mb = pd.to_numeric(original_sizes["OriginalMB"], errors="coerce").dropna()
    series_bytes = pd.to_numeric(original_sizes["OriginalBytes"], errors="coerce").dropna()

    if series_mb.empty or series_bytes.empty:
        print("No valid baseline/original size values available.")
        return

    print("\nBaseline original archive size")
    print("=" * 120)
    print(f"N packages:        {len(series_mb):,}")
    print(f"Mean MB:           {series_mb.mean():,.4f}")
    print(f"Median MB:         {series_mb.median():,.4f}")
    print(f"Q3 MB:             {series_mb.quantile(0.75):,.4f}")
    print(f"Total MB:          {series_bytes.sum() / (1024 * 1024):,.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize xz, zstd, zopfli, and brotli grid-search CSVs and generate plots."
        )
    )
    parser.add_argument(
        "--xz-dir",
        default=DEFAULT_XZ_DIR,
        help=f"Directory with xz grid-search CSVs. Default: {DEFAULT_XZ_DIR}",
    )
    parser.add_argument(
        "--zstd-dir",
        default=DEFAULT_ZSTD_DIR,
        help=f"Directory with zstd grid-search CSVs. Default: {DEFAULT_ZSTD_DIR}",
    )
    parser.add_argument(
        "--zopfli-dir",
        default=DEFAULT_ZOPFLI_DIR,
        help=f"Directory with zopfli grid-search CSVs. Default: {DEFAULT_ZOPFLI_DIR}",
    )
    parser.add_argument(
        "--brotli-dir",
        default=DEFAULT_BROTLI_DIR,
        help=f"Directory with brotli grid-search CSVs. Default: {DEFAULT_BROTLI_DIR}",
    )
    parser.add_argument(
        "--size-csv",
        default=DEFAULT_SIZE_CSV,
        help=(
            "CSV with OriginalBytes for computing gains. "
            f"Default: {DEFAULT_SIZE_CSV}"
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory where summaries and plots are written. Default: {DEFAULT_OUTPUT_DIR}",
    )

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    xz = load_grid_search_results(Path(args.xz_dir), "xz")
    zstd = load_grid_search_results(Path(args.zstd_dir), "zstd")
    zopfli = load_grid_search_results(Path(args.zopfli_dir), "zopfli")
    brotli = load_grid_search_results(Path(args.brotli_dir), "brotli")

    frames = [df for df in [xz, zstd, zopfli, brotli] if not df.empty]

    if not frames:
        raise RuntimeError("No grid-search results found.")

    grid = pd.concat(frames, ignore_index=True)

    original_sizes = load_original_sizes(Path(args.size_csv))
    grid = add_original_size_and_gain(grid, original_sizes)
    grid = add_larger_no_gain_analysis(grid)

    print_baseline_summary(original_sizes)

    summary = summarize_group(grid)
    stats = descriptive_stats_by_config(grid)

    grid_path = output_dir / "grid_search_all_results_normalized.csv"
    summary_path = output_dir / "grid_search_summary_by_config.csv"
    stats_path = output_dir / "grid_search_descriptive_statistics_by_config.csv"

    grid.to_csv(grid_path, index=False)
    summary.to_csv(summary_path, index=False)
    stats.to_csv(stats_path, index=False)

    print("\nGrid-search files loaded")
    print("=" * 120)
    print(f"xz rows: {len(xz)}")
    print(f"zstd rows: {len(zstd)}")
    print(f"zopfli rows: {len(zopfli)}")
    print(f"brotli rows: {len(brotli)}")
    print(f"total rows: {len(grid)}")

    print("\nSummary by config")
    print("=" * 120)

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 220)
    pd.set_option("display.float_format", "{:,.4f}".format)

    if summary.empty:
        print("No summary available.")
    else:
        print(summary_for_print(summary).to_string(index=False))

    print_descriptive_stats(stats)

    create_plots(summary, output_dir)
    create_combined_plots(summary, output_dir)

    print("\nOutput")
    print("=" * 120)
    print(f"Normalized results CSV: {grid_path}")
    print(f"Summary CSV: {summary_path}")
    print(f"Descriptive stats CSV: {stats_path}")
    print(f"Plots directory: {output_dir}")
    print("\nCombined ordinal plots:")
    print(f"- {output_dir / 'combined_median_size_over_ordinal_parameter.png'}")
    print(f"- {output_dir / 'combined_median_compression_time_over_ordinal_parameter.png'}")
    print(f"- {output_dir / 'combined_num_packages_with_size_gain_over_ordinal_parameter.png'}")
    print(f"- {output_dir / 'combined_smallest_original_mb_with_no_larger_no_gain_over_ordinal_parameter.png'}")


if __name__ == "__main__":
    main()