#!/usr/bin/env python3

import argparse
from pathlib import Path
from typing import Dict, Optional

import pandas as pd


DEFAULT_ORIGINAL_DIR = "../data/npm_tarballs_2500"
DEFAULT_UNPACKED_DIR = "../data/unpacked_2500"
DEFAULT_XZ_DIR = "../data/repacked_xz_2500"
DEFAULT_ZSTD_DIR = "../data/repacked_zstd_2500"
DEFAULT_ZOPFLI_DIR = "../data/repacked_zopfli_2500"

DEFAULT_XZ_TIMINGS_CSV = "../data/repacked_xz_2500/compression_timings_xz.csv"
DEFAULT_ZSTD_TIMINGS_CSV = "../data/repacked_zstd_2500/compression_timings_zstd.csv"
DEFAULT_ZOPFLI_TIMINGS_CSV = "../data/repacked_zopfli_2500/compression_timings_zopfli.csv"

DEFAULT_OUTPUT_CSV = "../data/package_size_comparison_2500.csv"


def file_size_bytes(path: Path) -> int:
    return path.stat().st_size


def directory_size_bytes(path: Path) -> int:
    total = 0

    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size

    return total


def strip_known_suffix(filename: str) -> str:
    suffixes = [
        ".tar.xz",
        ".tar.zst",
        ".tgz",
        ".tar.gz",
    ]

    for suffix in suffixes:
        if filename.endswith(suffix):
            return filename[: -len(suffix)]

    return filename


def collect_file_sizes(directory: Path, patterns: list[str]) -> Dict[str, int]:
    sizes: Dict[str, int] = {}

    if not directory.exists():
        print(f"WARNING: directory does not exist: {directory}")
        return sizes

    for pattern in patterns:
        for path in directory.glob(pattern):
            if path.is_file():
                key = strip_known_suffix(path.name)
                sizes[key] = file_size_bytes(path)

    return sizes


def collect_unpacked_sizes(directory: Path) -> Dict[str, int]:
    sizes: Dict[str, int] = {}

    if not directory.exists():
        print(f"WARNING: directory does not exist: {directory}")
        return sizes

    for path in directory.iterdir():
        if path.is_dir():
            sizes[path.name] = directory_size_bytes(path)

    return sizes


def collect_timings(timings_csv: Path) -> Dict[str, float]:
    """
    Reads a timings CSV produced by compression scripts.

    Expected columns:
      PackageName,ElapsedMilliseconds

    Also tolerates:
      PackageKey,ElapsedMilliseconds
      PackageName,ElapsedSeconds
      PackageKey,ElapsedSeconds

    Returned values are always milliseconds.
    """
    timings: Dict[str, float] = {}

    if not timings_csv.exists():
        print(f"WARNING: timings CSV does not exist: {timings_csv}")
        return timings

    df = pd.read_csv(timings_csv, keep_default_na=False)

    key_column = None
    if "PackageName" in df.columns:
        key_column = "PackageName"
    elif "PackageKey" in df.columns:
        key_column = "PackageKey"

    if key_column is None:
        print(f"WARNING: no PackageName/PackageKey column in timings CSV: {timings_csv}")
        return timings

    elapsed_column = None
    if "ElapsedMilliseconds" in df.columns:
        elapsed_column = "ElapsedMilliseconds"
    elif "ElapsedSeconds" in df.columns:
        elapsed_column = "ElapsedSeconds"

    if elapsed_column is None:
        print(
            f"WARNING: no ElapsedMilliseconds/ElapsedSeconds column in timings CSV: "
            f"{timings_csv}"
        )
        return timings

    df[elapsed_column] = pd.to_numeric(df[elapsed_column], errors="coerce")

    for _, row in df.iterrows():
        key = str(row[key_column]).strip()
        elapsed = row[elapsed_column]

        if key and pd.notna(elapsed):
            elapsed = float(elapsed)

            if elapsed_column == "ElapsedSeconds":
                elapsed *= 1000

            timings[key] = elapsed

    return timings


def bytes_to_mb(value: Optional[int]) -> Optional[float]:
    if value is None:
        return None
    return value / (1024 * 1024)


def percent_saving(new_size: Optional[int], old_size: Optional[int]) -> Optional[float]:
    """
    Percentage saved by new_size compared to old_size.

    Example:
      old_size = 100 MB
      new_size = 25 MB
      saving = 75%
    """
    if new_size is None or old_size is None or old_size == 0:
        return None
    return (1 - (new_size / old_size)) * 100


def throughput_mb_per_second(
    input_mb: Optional[float],
    elapsed_ms: Optional[float],
) -> Optional[float]:
    if input_mb is None or elapsed_ms is None or elapsed_ms <= 0:
        return None

    elapsed_seconds = elapsed_ms / 1000
    return input_mb / elapsed_seconds


def speedup_ratio(
    baseline_ms: Optional[float],
    comparison_ms: Optional[float],
) -> Optional[float]:
    """
    Returns how many times comparison is faster than baseline.

    Example:
      baseline_ms = 1000
      comparison_ms = 250
      result = 4.0

    Meaning:
      comparison is 4x faster than baseline.
    """
    if baseline_ms is None or comparison_ms is None or comparison_ms <= 0:
        return None
    return baseline_ms / comparison_ms


def build_comparison(
    original: Dict[str, int],
    unpacked: Dict[str, int],
    xz: Dict[str, int],
    zstd: Dict[str, int],
    zopfli: Dict[str, int],
    xz_timings: Dict[str, float],
    zstd_timings: Dict[str, float],
    zopfli_timings: Dict[str, float],
) -> pd.DataFrame:
    all_keys = sorted(
        set(original)
        | set(unpacked)
        | set(xz)
        | set(zstd)
        | set(zopfli)
        | set(xz_timings)
        | set(zstd_timings)
        | set(zopfli_timings)
    )

    rows = []

    for package_key in all_keys:
        original_size = original.get(package_key)
        unpacked_size = unpacked.get(package_key)
        xz_size = xz.get(package_key)
        zstd_size = zstd.get(package_key)
        zopfli_size = zopfli.get(package_key)

        original_mb = bytes_to_mb(original_size)
        unpacked_mb = bytes_to_mb(unpacked_size)
        xz_mb = bytes_to_mb(xz_size)
        zstd_mb = bytes_to_mb(zstd_size)
        zopfli_mb = bytes_to_mb(zopfli_size)

        xz_elapsed_ms = xz_timings.get(package_key)
        zstd_elapsed_ms = zstd_timings.get(package_key)
        zopfli_elapsed_ms = zopfli_timings.get(package_key)

        rows.append(
            {
                "PackageKey": package_key,

                "OriginalBytes": original_size,
                "UnpackedBytes": unpacked_size,
                "XzBytes": xz_size,
                "ZstdBytes": zstd_size,
                "ZopfliBytes": zopfli_size,

                "OriginalMB": original_mb,
                "UnpackedMB": unpacked_mb,
                "XzMB": xz_mb,
                "ZstdMB": zstd_mb,
                "ZopfliMB": zopfli_mb,

                "XzElapsedMilliseconds": xz_elapsed_ms,
                "ZstdElapsedMilliseconds": zstd_elapsed_ms,
                "ZopfliElapsedMilliseconds": zopfli_elapsed_ms,

                "XzThroughputUnpackedMBPerSecond": throughput_mb_per_second(
                    unpacked_mb,
                    xz_elapsed_ms,
                ),
                "ZstdThroughputUnpackedMBPerSecond": throughput_mb_per_second(
                    unpacked_mb,
                    zstd_elapsed_ms,
                ),
                "ZopfliThroughputUnpackedMBPerSecond": throughput_mb_per_second(
                    unpacked_mb,
                    zopfli_elapsed_ms,
                ),

                "ZstdSpeedupVsXz": speedup_ratio(
                    xz_elapsed_ms,
                    zstd_elapsed_ms,
                ),
                "ZopfliSpeedupVsXz": speedup_ratio(
                    xz_elapsed_ms,
                    zopfli_elapsed_ms,
                ),
                "ZstdSpeedupVsZopfli": speedup_ratio(
                    zopfli_elapsed_ms,
                    zstd_elapsed_ms,
                ),
                "XzSpeedupVsZopfli": speedup_ratio(
                    zopfli_elapsed_ms,
                    xz_elapsed_ms,
                ),

                "OriginalSavingVsUnpackedPercent": percent_saving(
                    original_size,
                    unpacked_size,
                ),
                "XzSavingVsUnpackedPercent": percent_saving(
                    xz_size,
                    unpacked_size,
                ),
                "ZstdSavingVsUnpackedPercent": percent_saving(
                    zstd_size,
                    unpacked_size,
                ),
                "ZopfliSavingVsUnpackedPercent": percent_saving(
                    zopfli_size,
                    unpacked_size,
                ),

                "XzSavingVsOriginalPercent": percent_saving(
                    xz_size,
                    original_size,
                ),
                "ZstdSavingVsOriginalPercent": percent_saving(
                    zstd_size,
                    original_size,
                ),
                "ZopfliSavingVsOriginalPercent": percent_saving(
                    zopfli_size,
                    original_size,
                ),
            }
        )

    return pd.DataFrame(rows)


def summarize_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    existing_columns = [column for column in columns if column in df.columns]

    if not existing_columns:
        return pd.DataFrame()

    stats = df[existing_columns].describe(percentiles=[0.25, 0.5, 0.75]).T

    stats = stats.rename(
        columns={
            "count": "Count",
            "mean": "Mean",
            "std": "StdDev",
            "min": "Min",
            "25%": "Q1",
            "50%": "Median",
            "75%": "Q3",
            "max": "Max",
        }
    )

    stats["IQR"] = stats["Q3"] - stats["Q1"]

    return stats[["Count", "Min", "Q1", "Median", "Q3", "Max", "Mean", "StdDev", "IQR"]]


def print_total_sizes(df: pd.DataFrame, size_columns_bytes: list[str]) -> None:
    print("\nTotal size")
    print("=" * 80)

    for column in size_columns_bytes:
        total_bytes = df[column].dropna().sum()
        total_mb = total_bytes / (1024 * 1024)
        print(f"{column}: {total_bytes:,.0f} bytes ({total_mb:,.2f} MB)")


def print_total_times(df: pd.DataFrame, timing_columns: list[str]) -> None:
    print("\nTotal compression time")
    print("=" * 80)

    for column in timing_columns:
        total_ms = df[column].dropna().sum()
        print(
            f"{column}: "
            f"{total_ms:,.2f} ms "
            f"({total_ms / 1000:,.2f} seconds, {total_ms / 60000:,.2f} minutes)"
        )


def print_time_comparison_summary(df: pd.DataFrame) -> None:
    timing_columns = [
        "XzElapsedMilliseconds",
        "ZstdElapsedMilliseconds",
        "ZopfliElapsedMilliseconds",
    ]

    throughput_columns = [
        "XzThroughputUnpackedMBPerSecond",
        "ZstdThroughputUnpackedMBPerSecond",
        "ZopfliThroughputUnpackedMBPerSecond",
    ]

    speedup_columns = [
        "ZstdSpeedupVsXz",
        "ZopfliSpeedupVsXz",
        "ZstdSpeedupVsZopfli",
        "XzSpeedupVsZopfli",
    ]

    print("\nDescriptive statistics - compression times in milliseconds")
    print("=" * 80)
    timing_stats = summarize_columns(df, timing_columns)
    print("No timing statistics available." if timing_stats.empty else timing_stats.to_string())

    print("\nDescriptive statistics - throughput in unpacked MB/s")
    print("=" * 80)
    throughput_stats = summarize_columns(df, throughput_columns)
    print(
        "No throughput statistics available."
        if throughput_stats.empty
        else throughput_stats.to_string()
    )

    print("\nDescriptive statistics - compression speedups")
    print("=" * 80)
    speedup_stats = summarize_columns(df, speedup_columns)
    print("No speedup statistics available." if speedup_stats.empty else speedup_stats.to_string())

    matched = df[
        df["XzElapsedMilliseconds"].notna()
        & df["ZstdElapsedMilliseconds"].notna()
        & df["ZopfliElapsedMilliseconds"].notna()
    ].copy()

    print("\nPer-package fastest compressor")
    print("=" * 80)

    if matched.empty:
        print("No packages have timing data for all compressors.")
        return

    fastest_counts = {
        "xz": 0,
        "zstd": 0,
        "zopfli": 0,
    }

    for _, row in matched.iterrows():
        values = {
            "xz": row["XzElapsedMilliseconds"],
            "zstd": row["ZstdElapsedMilliseconds"],
            "zopfli": row["ZopfliElapsedMilliseconds"],
        }

        fastest = min(values, key=values.get)
        fastest_counts[fastest] += 1

    for name, count in fastest_counts.items():
        percent = (count / len(matched)) * 100
        print(f"{name}: {count} packages ({percent:.2f}%)")

    print(f"Compared packages with all timing data: {len(matched)}")


def print_summary(df: pd.DataFrame) -> None:
    size_columns_bytes = [
        "OriginalBytes",
        "UnpackedBytes",
        "XzBytes",
        "ZstdBytes",
        "ZopfliBytes",
    ]

    size_columns_mb = [
        "OriginalMB",
        "UnpackedMB",
        "XzMB",
        "ZstdMB",
        "ZopfliMB",
    ]

    saving_columns = [
        "OriginalSavingVsUnpackedPercent",
        "XzSavingVsUnpackedPercent",
        "ZstdSavingVsUnpackedPercent",
        "ZopfliSavingVsUnpackedPercent",
        "XzSavingVsOriginalPercent",
        "ZstdSavingVsOriginalPercent",
        "ZopfliSavingVsOriginalPercent",
    ]

    timing_columns = [
        "XzElapsedMilliseconds",
        "ZstdElapsedMilliseconds",
        "ZopfliElapsedMilliseconds",
    ]

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 220)
    pd.set_option("display.float_format", "{:,.4f}".format)

    print("\nCounts")
    print("=" * 80)
    print(f"Packages in comparison table: {len(df)}")

    for column in size_columns_bytes:
        print(f"{column}: {df[column].notna().sum()} present")

    for column in timing_columns:
        print(f"{column}: {df[column].notna().sum()} present")

    print_total_sizes(df, size_columns_bytes)
    print_total_times(df, timing_columns)

    print("\nDescriptive statistics - sizes in MB")
    print("=" * 80)
    size_stats = summarize_columns(df, size_columns_mb)
    print("No size statistics available." if size_stats.empty else size_stats.to_string())

    print("\nDescriptive statistics - savings percentages")
    print("=" * 80)
    saving_stats = summarize_columns(df, saving_columns)
    print("No saving statistics available." if saving_stats.empty else saving_stats.to_string())

    print_time_comparison_summary(df)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compare package sizes and compression times across original, unpacked, "
            "xz, zstd, and zopfli versions."
        )
    )

    parser.add_argument(
        "--original-dir",
        default=DEFAULT_ORIGINAL_DIR,
        help=f"Directory with original npm .tgz files. Default: {DEFAULT_ORIGINAL_DIR}",
    )
    parser.add_argument(
        "--unpacked-dir",
        default=DEFAULT_UNPACKED_DIR,
        help=f"Directory with unpacked package folders. Default: {DEFAULT_UNPACKED_DIR}",
    )
    parser.add_argument(
        "--xz-dir",
        default=DEFAULT_XZ_DIR,
        help=f"Directory with .tar.xz files. Default: {DEFAULT_XZ_DIR}",
    )
    parser.add_argument(
        "--zstd-dir",
        default=DEFAULT_ZSTD_DIR,
        help=f"Directory with .tar.zst files. Default: {DEFAULT_ZSTD_DIR}",
    )
    parser.add_argument(
        "--zopfli-dir",
        default=DEFAULT_ZOPFLI_DIR,
        help=f"Directory with zopfli .tgz files. Default: {DEFAULT_ZOPFLI_DIR}",
    )
    parser.add_argument(
        "--xz-timings-csv",
        default=DEFAULT_XZ_TIMINGS_CSV,
        help=f"CSV with xz timings. Default: {DEFAULT_XZ_TIMINGS_CSV}",
    )
    parser.add_argument(
        "--zstd-timings-csv",
        default=DEFAULT_ZSTD_TIMINGS_CSV,
        help=f"CSV with zstd timings. Default: {DEFAULT_ZSTD_TIMINGS_CSV}",
    )
    parser.add_argument(
        "--zopfli-timings-csv",
        default=DEFAULT_ZOPFLI_TIMINGS_CSV,
        help=f"CSV with zopfli timings. Default: {DEFAULT_ZOPFLI_TIMINGS_CSV}",
    )
    parser.add_argument(
        "-o",
        "--output-csv",
        default=DEFAULT_OUTPUT_CSV,
        help=f"Output CSV. Default: {DEFAULT_OUTPUT_CSV}",
    )

    args = parser.parse_args()

    original = collect_file_sizes(Path(args.original_dir), ["*.tgz", "*.tar.gz"])
    unpacked = collect_unpacked_sizes(Path(args.unpacked_dir))
    xz = collect_file_sizes(Path(args.xz_dir), ["*.tar.xz"])
    zstd = collect_file_sizes(Path(args.zstd_dir), ["*.tar.zst"])
    zopfli = collect_file_sizes(Path(args.zopfli_dir), ["*.tgz", "*.tar.gz"])

    xz_timings = collect_timings(Path(args.xz_timings_csv))
    zstd_timings = collect_timings(Path(args.zstd_timings_csv))
    zopfli_timings = collect_timings(Path(args.zopfli_timings_csv))

    df = build_comparison(
        original=original,
        unpacked=unpacked,
        xz=xz,
        zstd=zstd,
        zopfli=zopfli,
        xz_timings=xz_timings,
        zstd_timings=zstd_timings,
        zopfli_timings=zopfli_timings,
    )

    output_csv = Path(args.output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv, index=False)

    print_summary(df)

    print("\nOutput")
    print("=" * 80)
    print(f"Wrote: {output_csv}")


if __name__ == "__main__":
    main()