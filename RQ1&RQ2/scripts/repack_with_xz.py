#!/usr/bin/env python3

import argparse
import csv
import shutil
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path


DEFAULT_UNPACKED_DIR = "../data/unpacked_2500"
DEFAULT_OUTPUT_DIR = "../data/repacked_xz_2500"


def check_xz_available() -> None:
    if shutil.which("xz") is None:
        raise RuntimeError(
            "xz not found. Install it first, e.g. `sudo apt install xz-utils` "
            "or `brew install xz`."
        )


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


def compress_with_xz(
    tar_path: Path,
    output_tar_xz: Path,
    level: int,
    extreme: bool,
    threads: int,
) -> None:
    if output_tar_xz.exists():
        output_tar_xz.unlink()

    cmd = [
        "xz",
        f"-{level}",
        "-k",
        "-f",
        "-c",
    ]

    if extreme:
        cmd.append("-e")

    if threads >= 0:
        cmd.append(f"-T{threads}")

    cmd.append(str(tar_path))

    with output_tar_xz.open("wb") as out:
        subprocess.run(cmd, check=True, stdout=out)


def write_timings_csv(output_path: Path, rows: list[dict]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "PackageName",
        "Status",
        "InputPath",
        "OutputPath",
        "OutputBytes",
        "ElapsedMilliseconds",
    ]

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def repack_one(
    package_dir: Path,
    output_dir: Path,
    level: int,
    extreme: bool,
    threads: int,
    overwrite: bool,
) -> tuple[str, float, int, Path]:
    output_tar_xz = output_dir / f"{package_dir.name}.tar.xz"

    if output_tar_xz.exists() and not overwrite:
        output_bytes = output_tar_xz.stat().st_size
        return "skipped_existing", 0.0, output_bytes, output_tar_xz

    start = time.perf_counter()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        tar_path = tmp_dir / f"{package_dir.name}.tar"

        create_uncompressed_tar(package_dir, tar_path)
        compress_with_xz(
            tar_path=tar_path,
            output_tar_xz=output_tar_xz,
            level=level,
            extreme=extreme,
            threads=threads,
        )

    elapsed_ms = (time.perf_counter() - start) * 1000
    output_bytes = output_tar_xz.stat().st_size if output_tar_xz.exists() else 0

    return "repacked", elapsed_ms, output_bytes, output_tar_xz


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Repack unpacked npm packages as .tar.xz files using xz."
    )
    parser.add_argument(
        "--unpacked-dir",
        default=DEFAULT_UNPACKED_DIR,
        help=f"Directory containing unpacked package folders. Default: {DEFAULT_UNPACKED_DIR}",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Existing directory where .tar.xz files will be written. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--level",
        type=int,
        default=9,
        help="xz compression level, from 0 to 9. Default: 6",
    )
    parser.add_argument(
        "--extreme",
        action="store_true",
        help="Use xz extreme mode (-e). Slower, sometimes slightly smaller.",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=0,
        help="Number of xz threads. 0 means automatic. Default: 0",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing .tar.xz files in the output directory.",
    )
    parser.add_argument(
        "--timings-csv",
        default=None,
        help=(
            "CSV file where per-package compression timings will be written. "
            "Default: <output-dir>/compression_timings_xz.csv"
        ),
    )

    args = parser.parse_args()

    check_xz_available()

    if args.level < 0 or args.level > 9:
        raise ValueError("xz level must be between 0 and 9.")

    if args.threads < 0:
        raise ValueError("threads must be >= 0. Use 0 for automatic.")

    unpacked_dir = Path(args.unpacked_dir)
    output_dir = Path(args.output_dir)

    if not unpacked_dir.exists():
        raise FileNotFoundError(f"Unpacked directory does not exist: {unpacked_dir}")

    if not output_dir.exists():
        raise FileNotFoundError(
            f"Output directory does not exist: {output_dir}\n"
            "Create it manually first, then rerun the script."
        )

    timings_csv = (
        Path(args.timings_csv)
        if args.timings_csv
        else output_dir / "compression_timings_xz.csv"
    )

    package_dirs = sorted([p for p in unpacked_dir.iterdir() if p.is_dir()])

    if not package_dirs:
        print(f"No package directories found in: {unpacked_dir}")
        return

    repacked = 0
    skipped_existing = 0
    failed = 0
    total_elapsed_ms = 0.0
    timing_rows = []

    for index, package_dir in enumerate(package_dirs, start=1):
        print(f"[{index}/{len(package_dirs)}] {package_dir.name}")

        output_tar_xz = output_dir / f"{package_dir.name}.tar.xz"

        try:
            status, elapsed_ms, output_bytes, output_path = repack_one(
                package_dir=package_dir,
                output_dir=output_dir,
                level=args.level,
                extreme=args.extreme,
                threads=args.threads,
                overwrite=args.overwrite,
            )

            total_elapsed_ms += elapsed_ms

            if status == "repacked":
                repacked += 1
                print(f"  repacked in {elapsed_ms:.2f} ms")
            elif status == "skipped_existing":
                skipped_existing += 1
                print("  skipped existing")

            timing_rows.append(
                {
                    "PackageName": package_dir.name,
                    "Status": status,
                    "InputPath": str(package_dir),
                    "OutputPath": str(output_path),
                    "OutputBytes": output_bytes,
                    "ElapsedMilliseconds": elapsed_ms,
                }
            )

        except subprocess.CalledProcessError as exc:
            failed += 1
            print(f"  ERROR: xz failed with exit code {exc.returncode}")

            timing_rows.append(
                {
                    "PackageName": package_dir.name,
                    "Status": "failed",
                    "InputPath": str(package_dir),
                    "OutputPath": str(output_tar_xz),
                    "OutputBytes": 0,
                    "ElapsedMilliseconds": 0.0,
                }
            )

        except Exception as exc:
            failed += 1
            print(f"  ERROR: {exc}")

            timing_rows.append(
                {
                    "PackageName": package_dir.name,
                    "Status": "failed",
                    "InputPath": str(package_dir),
                    "OutputPath": str(output_tar_xz),
                    "OutputBytes": 0,
                    "ElapsedMilliseconds": 0.0,
                }
            )

    write_timings_csv(timings_csv, timing_rows)

    print("\nSummary")
    print("=" * 80)
    print(f"Package folders found: {len(package_dirs)}")
    print(f"Repacked: {repacked}")
    print(f"Skipped existing: {skipped_existing}")
    print(f"Failed: {failed}")
    print(
        f"Total measured compression time: "
        f"{total_elapsed_ms:,.2f} ms ({total_elapsed_ms / 1000:,.2f} seconds)"
    )
    print(f"Output directory: {output_dir}")
    print(f"Timings CSV: {timings_csv}")


if __name__ == "__main__":
    main()