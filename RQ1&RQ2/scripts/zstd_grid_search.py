#!/usr/bin/env python3

import argparse
import csv
import shutil
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Dict, List


DEFAULT_UNPACKED_DIR = "../data/unpacked_2500"
DEFAULT_OUTPUT_DIR = "../data/zstd_grid_search"
DEFAULT_LEVELS = "1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22"

OUTPUT_COLUMNS = [
    "PackageKey",
    "ConfigName",
    "Level",
    "Ultra",
    "Threads",
    "Status",
    "InputDir",
    "UnpackedBytes",
    "OutputArchive",
    "ZstdBytes",
    "ZstdMB",
    "ElapsedMilliseconds",
    "Command",
    "Error",
]


def check_zstd_available() -> None:
    if shutil.which("zstd") is None:
        raise RuntimeError(
            "zstd not found. Install it first, e.g. `sudo apt install zstd` "
            "or `brew install zstd`."
        )


def parse_levels(value: str) -> List[int]:
    levels = []

    for item in value.split(","):
        item = item.strip()

        if not item:
            continue

        level = int(item)

        if level < 1 or level > 22:
            raise ValueError("zstd levels must be between 1 and 22.")

        levels.append(level)

    if not levels:
        raise ValueError("No zstd levels provided.")

    return levels


def directory_size_bytes(path: Path) -> int:
    total = 0

    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size

    return total


def config_name(level: int, ultra: bool) -> str:
    if ultra:
        return f"zstd_l{level}_ultra"
    return f"zstd_l{level}"


def config_csv_path(output_dir: Path, level: int, ultra: bool) -> Path:
    return output_dir / f"{config_name(level, ultra)}_results.csv"


def config_archive_dir(output_dir: Path, level: int, ultra: bool) -> Path:
    return output_dir / config_name(level, ultra) / "archives"


def ensure_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists() and path.stat().st_size > 0:
        return

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()


def load_done_successes(path: Path) -> set[str]:
    if not path.exists() or path.stat().st_size == 0:
        return set()

    done = set()

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            package_key = str(row.get("PackageKey", "")).strip()
            status = str(row.get("Status", "")).strip()

            if package_key and status == "success":
                done.add(package_key)

    return done


def append_row(path: Path, row: Dict[str, object]) -> None:
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writerow(row)


def create_uncompressed_tar(package_dir: Path, tar_path: Path) -> None:
    """
    Create an uncompressed .tar with npm-like internal structure:

      package/
        package.json
        ...
    """
    with tarfile.open(tar_path, "w") as tar:
        for item in sorted(package_dir.rglob("*")):
            arcname = Path("package") / item.relative_to(package_dir)
            tar.add(item, arcname=str(arcname), recursive=False)


def build_zstd_command(
    tar_path: Path,
    output_tar_zst: Path,
    level: int,
    ultra: bool,
    threads: int,
) -> List[str]:
    cmd = [
        "zstd",
        "-f",
        "-o",
        str(output_tar_zst),
    ]

    if threads >= 0:
        cmd.insert(1, f"-T{threads}")

    if ultra:
        cmd.insert(1, "--ultra")

    cmd.insert(1, f"-{level}")

    cmd.append(str(tar_path))

    return cmd


def compress_with_zstd(
    tar_path: Path,
    output_tar_zst: Path,
    level: int,
    ultra: bool,
    threads: int,
) -> List[str]:
    if output_tar_zst.exists():
        output_tar_zst.unlink()

    cmd = build_zstd_command(
        tar_path=tar_path,
        output_tar_zst=output_tar_zst,
        level=level,
        ultra=ultra,
        threads=threads,
    )

    subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    return cmd


def measure_one(
    package_dir: Path,
    output_dir: Path,
    level: int,
    ultra: bool,
    threads: int,
    keep_archives: bool,
) -> Dict[str, object]:
    package_key = package_dir.name
    cfg_name = config_name(level, ultra)
    unpacked_bytes = directory_size_bytes(package_dir)

    archive_dir = config_archive_dir(output_dir, level, ultra)
    output_archive = archive_dir / f"{package_key}.tar.zst"

    if keep_archives:
        archive_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f"zstd_grid_{package_key}_") as tmp:
        tmp_dir = Path(tmp)
        tar_path = tmp_dir / f"{package_key}.tar"

        if keep_archives:
            effective_output_archive = output_archive
        else:
            effective_output_archive = tmp_dir / f"{package_key}.tar.zst"

        start = time.perf_counter()
        command_text = ""

        try:
            create_uncompressed_tar(package_dir, tar_path)

            cmd = compress_with_zstd(
                tar_path=tar_path,
                output_tar_zst=effective_output_archive,
                level=level,
                ultra=ultra,
                threads=threads,
            )

            elapsed_ms = (time.perf_counter() - start) * 1000
            zstd_bytes = (
                effective_output_archive.stat().st_size
                if effective_output_archive.exists()
                else 0
            )

            command_text = " ".join(cmd)

            return {
                "PackageKey": package_key,
                "ConfigName": cfg_name,
                "Level": level,
                "Ultra": ultra,
                "Threads": threads,
                "Status": "success",
                "InputDir": str(package_dir),
                "UnpackedBytes": unpacked_bytes,
                "OutputArchive": str(output_archive if keep_archives else ""),
                "ZstdBytes": zstd_bytes,
                "ZstdMB": zstd_bytes / (1024 * 1024),
                "ElapsedMilliseconds": elapsed_ms,
                "Command": command_text,
                "Error": "",
            }

        except subprocess.CalledProcessError as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            stderr = ""

            if exc.stderr:
                try:
                    stderr = exc.stderr.decode("utf-8", errors="replace")
                except AttributeError:
                    stderr = str(exc.stderr)

            return {
                "PackageKey": package_key,
                "ConfigName": cfg_name,
                "Level": level,
                "Ultra": ultra,
                "Threads": threads,
                "Status": "failed",
                "InputDir": str(package_dir),
                "UnpackedBytes": unpacked_bytes,
                "OutputArchive": str(output_archive if keep_archives else ""),
                "ZstdBytes": "",
                "ZstdMB": "",
                "ElapsedMilliseconds": elapsed_ms,
                "Command": command_text,
                "Error": f"zstd failed with exit code {exc.returncode}: {stderr[:1000]}",
            }

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000

            return {
                "PackageKey": package_key,
                "ConfigName": cfg_name,
                "Level": level,
                "Ultra": ultra,
                "Threads": threads,
                "Status": "failed",
                "InputDir": str(package_dir),
                "UnpackedBytes": unpacked_bytes,
                "OutputArchive": str(output_archive if keep_archives else ""),
                "ZstdBytes": "",
                "ZstdMB": "",
                "ElapsedMilliseconds": elapsed_ms,
                "Command": command_text,
                "Error": str(exc),
            }


def build_configs(levels: List[int], include_ultra: bool) -> List[tuple[int, bool]]:
    configs = []

    for level in levels:
        if level <= 19:
            configs.append((level, False))
        else:
            configs.append((level, True))

    if include_ultra:
        for level in levels:
            configs.append((level, True))

    seen = set()
    unique_configs = []

    for config in configs:
        if config not in seen:
            unique_configs.append(config)
            seen.add(config)

    return unique_configs


def print_config_summary(
    csv_path: Path,
    level: int,
    ultra: bool,
    total_packages: int,
    done_successes: set[str],
) -> None:
    print("\nConfig")
    print("=" * 100)
    print(f"Config: {config_name(level, ultra)}")
    print(f"CSV: {csv_path}")
    print(f"Already completed successfully: {len(done_successes)}/{total_packages}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Grid search zstd compression levels for unpacked npm packages. "
            "Each zstd configuration gets a dedicated CSV with size and timing."
        )
    )
    parser.add_argument(
        "--unpacked-dir",
        default=DEFAULT_UNPACKED_DIR,
        help=f"Directory containing unpacked package folders. Default: {DEFAULT_UNPACKED_DIR}",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory where grid-search CSVs and optional archives are written. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--levels",
        default=DEFAULT_LEVELS,
        help=f"Comma-separated zstd levels to test, each 1-22. Default: {DEFAULT_LEVELS}",
    )
    parser.add_argument(
        "--include-ultra",
        action="store_true",
        help=(
            "Also test --ultra for every selected level. "
            "Levels 20-22 always use --ultra."
        ),
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=0,
        help="Number of zstd threads. 0 means automatic. Default: 0",
    )
    parser.add_argument(
        "--keep-archives",
        action="store_true",
        help=(
            "Keep the compressed .tar.zst archives. By default archives are created "
            "in a temporary directory and deleted after size/time are recorded."
        ),
    )
    parser.add_argument(
        "--only-config",
        default=None,
        help=(
            "Run only one config name, e.g. zstd_l19 or zstd_l22_ultra. "
            "Useful for resuming a specific configuration."
        ),
    )

    args = parser.parse_args()

    check_zstd_available()

    if args.threads < 0:
        raise ValueError("threads must be >= 0. Use 0 for automatic.")

    levels = parse_levels(args.levels)
    configs = build_configs(levels, args.include_ultra)

    if args.only_config:
        configs = [
            (level, ultra)
            for level, ultra in configs
            if config_name(level, ultra) == args.only_config
        ]

        if not configs:
            raise ValueError(
                f"No config matched --only-config {args.only_config!r}. "
                "Example values: zstd_l19, zstd_l22_ultra"
            )

    unpacked_dir = Path(args.unpacked_dir)
    output_dir = Path(args.output_dir)

    if not unpacked_dir.exists():
        raise FileNotFoundError(f"Unpacked directory does not exist: {unpacked_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    package_dirs = sorted([p for p in unpacked_dir.iterdir() if p.is_dir()])

    if not package_dirs:
        print(f"No package directories found in: {unpacked_dir}")
        return

    print("Zstd grid search")
    print("=" * 100)
    print(f"Unpacked dir: {unpacked_dir}")
    print(f"Output dir: {output_dir}")
    print(f"Packages: {len(package_dirs)}")
    print(f"Levels: {', '.join(str(level) for level in levels)}")
    print(f"Include ultra for all levels: {args.include_ultra}")
    print(f"Threads: {args.threads}")
    print(f"Keep archives: {args.keep_archives}")
    print(f"Configs: {', '.join(config_name(l, u) for l, u in configs)}")

    global_start = time.perf_counter()

    for level, ultra in configs:
        csv_path = config_csv_path(output_dir, level, ultra)
        ensure_csv(csv_path)

        done_successes = load_done_successes(csv_path)

        print_config_summary(
            csv_path=csv_path,
            level=level,
            ultra=ultra,
            total_packages=len(package_dirs),
            done_successes=done_successes,
        )

        completed = 0
        skipped = 0
        failed = 0
        total_elapsed_ms = 0.0

        for index, package_dir in enumerate(package_dirs, start=1):
            package_key = package_dir.name

            if package_key in done_successes:
                skipped += 1
                print(
                    f"[{index}/{len(package_dirs)}] {package_key} "
                    f"SKIP success already recorded"
                )
                continue

            print(
                f"[{index}/{len(package_dirs)}] {package_key} "
                f"level={level} ultra={ultra}"
            )

            row = measure_one(
                package_dir=package_dir,
                output_dir=output_dir,
                level=level,
                ultra=ultra,
                threads=args.threads,
                keep_archives=args.keep_archives,
            )

            append_row(csv_path, row)

            elapsed = row["ElapsedMilliseconds"]
            if isinstance(elapsed, (int, float)):
                total_elapsed_ms += float(elapsed)

            if row["Status"] == "success":
                completed += 1
                done_successes.add(package_key)
                print(
                    f"  success: {row['ZstdBytes']} bytes, "
                    f"{float(row['ElapsedMilliseconds']):.2f} ms"
                )
            else:
                failed += 1
                print(f"  failed: {row['Error']}")

        print("\nConfig summary")
        print("-" * 100)
        print(f"Config: {config_name(level, ultra)}")
        print(f"Completed this run: {completed}")
        print(f"Skipped successes: {skipped}")
        print(f"Failed this run: {failed}")
        print(
            f"Measured time this config: "
            f"{total_elapsed_ms:,.2f} ms "
            f"({total_elapsed_ms / 1000:,.2f} seconds)"
        )

    global_elapsed = time.perf_counter() - global_start

    print("\nGrid search completed")
    print("=" * 100)
    print(f"Total wall time: {global_elapsed:,.2f} seconds ({global_elapsed / 60:,.2f} minutes)")
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()