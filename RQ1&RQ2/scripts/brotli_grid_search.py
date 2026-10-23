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
DEFAULT_OUTPUT_DIR = "../data/brotli_grid_search"
DEFAULT_QUALITIES = "1,2,3,4,5,6,7,8,9,10,11"
DEFAULT_LGWINS = "24"

OUTPUT_COLUMNS = [
    "PackageKey",
    "ConfigName",
    "Quality",
    "Lgwin",
    "Status",
    "InputDir",
    "UnpackedBytes",
    "OutputArchive",
    "BrotliBytes",
    "BrotliMB",
    "ElapsedMilliseconds",
    "Command",
    "Error",
]


def check_brotli_available() -> None:
    if shutil.which("brotli") is None:
        raise RuntimeError(
            "brotli not found. Install it first, e.g. `sudo apt install brotli` "
            "or `brew install brotli`."
        )


def parse_int_list(
    value: str,
    name: str,
    min_value: int,
    max_value: int,
    allow_zero: bool = False,
) -> List[int]:
    values = []

    for item in value.split(","):
        item = item.strip()

        if not item:
            continue

        number = int(item)

        if allow_zero and number == 0:
            values.append(number)
            continue

        if number < min_value or number > max_value:
            raise ValueError(
                f"{name} values must be between {min_value} and {max_value}"
                + (" or 0" if allow_zero else "")
                + "."
            )

        values.append(number)

    if not values:
        raise ValueError(f"No {name} values provided.")

    return values


def directory_size_bytes(path: Path) -> int:
    total = 0

    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size

    return total


def config_name(quality: int, lgwin: int | None) -> str:
    if lgwin is None:
        return f"brotli_q{quality}_lgwin_default"

    return f"brotli_q{quality}_lgwin{lgwin}"


def config_csv_path(output_dir: Path, quality: int, lgwin: int | None) -> Path:
    return output_dir / f"{config_name(quality, lgwin)}_results.csv"


def config_archive_dir(output_dir: Path, quality: int, lgwin: int | None) -> Path:
    return output_dir / config_name(quality, lgwin) / "archives"


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


def build_brotli_command(
    tar_path: Path,
    output_tar_br: Path,
    quality: int,
    lgwin: int | None,
) -> List[str]:
    cmd = [
        "brotli",
        "-f",
        "-q",
        str(quality),
        "-o",
        str(output_tar_br),
    ]

    if lgwin is not None:
        cmd.extend(["-w", str(lgwin)])

    cmd.append(str(tar_path))

    return cmd


def compress_with_brotli(
    tar_path: Path,
    output_tar_br: Path,
    quality: int,
    lgwin: int | None,
) -> List[str]:
    if output_tar_br.exists():
        output_tar_br.unlink()

    cmd = build_brotli_command(
        tar_path=tar_path,
        output_tar_br=output_tar_br,
        quality=quality,
        lgwin=lgwin,
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
    quality: int,
    lgwin: int | None,
    keep_archives: bool,
) -> Dict[str, object]:
    package_key = package_dir.name
    cfg_name = config_name(quality, lgwin)
    unpacked_bytes = directory_size_bytes(package_dir)

    archive_dir = config_archive_dir(output_dir, quality, lgwin)
    output_archive = archive_dir / f"{package_key}.tar.br"

    if keep_archives:
        archive_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f"brotli_grid_{package_key}_") as tmp:
        tmp_dir = Path(tmp)
        tar_path = tmp_dir / f"{package_key}.tar"

        if keep_archives:
            effective_output_archive = output_archive
        else:
            effective_output_archive = tmp_dir / f"{package_key}.tar.br"

        start = time.perf_counter()
        command_text = ""

        try:
            create_uncompressed_tar(package_dir, tar_path)

            cmd = compress_with_brotli(
                tar_path=tar_path,
                output_tar_br=effective_output_archive,
                quality=quality,
                lgwin=lgwin,
            )

            elapsed_ms = (time.perf_counter() - start) * 1000
            brotli_bytes = (
                effective_output_archive.stat().st_size
                if effective_output_archive.exists()
                else 0
            )

            command_text = " ".join(cmd)

            return {
                "PackageKey": package_key,
                "ConfigName": cfg_name,
                "Quality": quality,
                "Lgwin": lgwin if lgwin is not None else "",
                "Status": "success",
                "InputDir": str(package_dir),
                "UnpackedBytes": unpacked_bytes,
                "OutputArchive": str(output_archive if keep_archives else ""),
                "BrotliBytes": brotli_bytes,
                "BrotliMB": brotli_bytes / (1024 * 1024),
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
                "Quality": quality,
                "Lgwin": lgwin if lgwin is not None else "",
                "Status": "failed",
                "InputDir": str(package_dir),
                "UnpackedBytes": unpacked_bytes,
                "OutputArchive": str(output_archive if keep_archives else ""),
                "BrotliBytes": "",
                "BrotliMB": "",
                "ElapsedMilliseconds": elapsed_ms,
                "Command": command_text,
                "Error": f"brotli failed with exit code {exc.returncode}: {stderr[:1000]}",
            }

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000

            return {
                "PackageKey": package_key,
                "ConfigName": cfg_name,
                "Quality": quality,
                "Lgwin": lgwin if lgwin is not None else "",
                "Status": "failed",
                "InputDir": str(package_dir),
                "UnpackedBytes": unpacked_bytes,
                "OutputArchive": str(output_archive if keep_archives else ""),
                "BrotliBytes": "",
                "BrotliMB": "",
                "ElapsedMilliseconds": elapsed_ms,
                "Command": command_text,
                "Error": str(exc),
            }


def build_configs(
    qualities: List[int],
    lgwins: List[int],
) -> List[tuple[int, int | None]]:
    configs = []

    for quality in qualities:
        for lgwin in lgwins:
            if lgwin == 0:
                configs.append((quality, None))
            else:
                configs.append((quality, lgwin))

    return configs


def print_config_summary(
    csv_path: Path,
    quality: int,
    lgwin: int | None,
    total_packages: int,
    done_successes: set[str],
) -> None:
    print("\nConfig")
    print("=" * 100)
    print(f"Config: {config_name(quality, lgwin)}")
    print(f"CSV: {csv_path}")
    print(f"Already completed successfully: {len(done_successes)}/{total_packages}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Grid search Brotli compression parameters for unpacked npm packages. "
            "Each Brotli configuration gets a dedicated CSV with size and timing."
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
        "--qualities",
        default=DEFAULT_QUALITIES,
        help=f"Comma-separated Brotli quality values, each 0-11. Default: {DEFAULT_QUALITIES}",
    )
    parser.add_argument(
        "--lgwins",
        default=DEFAULT_LGWINS,
        help=(
            "Comma-separated Brotli lgwin values, each 10-24. "
            "Use 0 to omit -w and use Brotli default. "
            f"Default: {DEFAULT_LGWINS}"
        ),
    )
    parser.add_argument(
        "--keep-archives",
        action="store_true",
        help=(
            "Keep the compressed .tar.br archives. By default archives are created "
            "in a temporary directory and deleted after size/time are recorded."
        ),
    )
    parser.add_argument(
        "--only-config",
        default=None,
        help=(
            "Run only one config name, e.g. brotli_q11_lgwin24 or "
            "brotli_q11_lgwin_default. Useful for resuming a specific configuration."
        ),
    )

    args = parser.parse_args()

    check_brotli_available()

    qualities = parse_int_list(
        value=args.qualities,
        name="Brotli quality",
        min_value=0,
        max_value=11,
    )

    lgwins = parse_int_list(
        value=args.lgwins,
        name="Brotli lgwin",
        min_value=10,
        max_value=24,
        allow_zero=True,
    )

    configs = build_configs(
        qualities=qualities,
        lgwins=lgwins,
    )

    if args.only_config:
        configs = [
            (quality, lgwin)
            for quality, lgwin in configs
            if config_name(quality, lgwin) == args.only_config
        ]

        if not configs:
            raise ValueError(
                f"No config matched --only-config {args.only_config!r}. "
                "Example values: brotli_q5_lgwin24, brotli_q11_lgwin24, "
                "brotli_q11_lgwin_default"
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

    print("Brotli grid search")
    print("=" * 100)
    print(f"Unpacked dir: {unpacked_dir}")
    print(f"Output dir: {output_dir}")
    print(f"Packages: {len(package_dirs)}")
    print(f"Qualities: {', '.join(str(q) for q in qualities)}")
    print(
        "Lgwins: "
        + ", ".join("default" if w == 0 else str(w) for w in lgwins)
    )
    print(f"Keep archives: {args.keep_archives}")
    print(f"Configs: {', '.join(config_name(q, w) for q, w in configs)}")

    global_start = time.perf_counter()

    for quality, lgwin in configs:
        csv_path = config_csv_path(output_dir, quality, lgwin)
        ensure_csv(csv_path)

        done_successes = load_done_successes(csv_path)

        print_config_summary(
            csv_path=csv_path,
            quality=quality,
            lgwin=lgwin,
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
                f"quality={quality} lgwin={lgwin if lgwin is not None else 'default'}"
            )

            row = measure_one(
                package_dir=package_dir,
                output_dir=output_dir,
                quality=quality,
                lgwin=lgwin,
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
                    f"  success: {row['BrotliBytes']} bytes, "
                    f"{float(row['ElapsedMilliseconds']):.2f} ms"
                )
            else:
                failed += 1
                print(f"  failed: {row['Error']}")

        print("\nConfig summary")
        print("-" * 100)
        print(f"Config: {config_name(quality, lgwin)}")
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
    print(
        f"Total wall time: "
        f"{global_elapsed:,.2f} seconds ({global_elapsed / 60:,.2f} minutes)"
    )
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()