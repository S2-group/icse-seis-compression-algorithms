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
DEFAULT_OUTPUT_DIR = "../data/repacked_brotli_2500"


def check_brotli_available() -> None:
    if shutil.which("brotli") is None:
        raise RuntimeError(
            "brotli not found. Install it first, e.g. `sudo apt install brotli` "
            "or `brew install brotli`."
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


def compress_with_brotli(
    tar_path: Path,
    output_tar_br: Path,
    quality: int,
    lgwin: int | None,
) -> None:
    """
    Compress an uncompressed .tar using Brotli.

    Typical max-compression settings:
      quality = 11
      lgwin = 24

    Brotli creates the output file directly with -o.
    """
    if output_tar_br.exists():
        output_tar_br.unlink()

    cmd = [
        "brotli",
        "-f",
        f"-q",
        str(quality),
        "-o",
        str(output_tar_br),
    ]

    if lgwin is not None:
        cmd.extend(["-w", str(lgwin)])

    cmd.append(str(tar_path))

    subprocess.run(cmd, check=True)


def write_timings_csv(output_path: Path, rows: list[dict]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "PackageName",
        "Status",
        "InputPath",
        "OutputPath",
        "OutputBytes",
        "ElapsedMilliseconds",
        "Quality",
        "Lgwin",
    ]

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def repack_one(
    package_dir: Path,
    output_dir: Path,
    quality: int,
    lgwin: int | None,
    overwrite: bool,
) -> tuple[str, float, int, Path]:
    output_tar_br = output_dir / f"{package_dir.name}.tar.br"

    if output_tar_br.exists() and not overwrite:
        output_bytes = output_tar_br.stat().st_size
        return "skipped_existing", 0.0, output_bytes, output_tar_br

    start = time.perf_counter()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        tar_path = tmp_dir / f"{package_dir.name}.tar"

        create_uncompressed_tar(package_dir, tar_path)
        compress_with_brotli(
            tar_path=tar_path,
            output_tar_br=output_tar_br,
            quality=quality,
            lgwin=lgwin,
        )

    elapsed_ms = (time.perf_counter() - start) * 1000
    output_bytes = output_tar_br.stat().st_size if output_tar_br.exists() else 0

    return "repacked", elapsed_ms, output_bytes, output_tar_br


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Repack unpacked npm packages as .tar.br files using Brotli."
    )
    parser.add_argument(
        "--unpacked-dir",
        default=DEFAULT_UNPACKED_DIR,
        help=f"Directory containing unpacked package folders. Default: {DEFAULT_UNPACKED_DIR}",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Existing directory where .tar.br files will be written. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=11,
        help="Brotli quality level, from 0 to 11. Default: 11",
    )
    parser.add_argument(
        "--lgwin",
        type=int,
        default=24,
        help=(
            "Brotli window size, from 10 to 24 for standard Brotli streams. "
            "Default: 24. Use --lgwin 0 to omit this parameter."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing .tar.br files in the output directory.",
    )
    parser.add_argument(
        "--timings-csv",
        default=None,
        help=(
            "CSV file where per-package compression timings will be written. "
            "Default: <output-dir>/compression_timings_brotli.csv"
        ),
    )

    args = parser.parse_args()

    check_brotli_available()

    if args.quality < 0 or args.quality > 11:
        raise ValueError("Brotli quality must be between 0 and 11.")

    if args.lgwin == 0:
        lgwin = None
    else:
        lgwin = args.lgwin

    if lgwin is not None and (lgwin < 10 or lgwin > 24):
        raise ValueError("Brotli lgwin must be between 10 and 24, or 0 to omit it.")

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
        else output_dir / "compression_timings_brotli.csv"
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

        output_tar_br = output_dir / f"{package_dir.name}.tar.br"

        try:
            status, elapsed_ms, output_bytes, output_path = repack_one(
                package_dir=package_dir,
                output_dir=output_dir,
                quality=args.quality,
                lgwin=lgwin,
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
                    "Quality": args.quality,
                    "Lgwin": lgwin if lgwin is not None else "",
                }
            )

        except subprocess.CalledProcessError as exc:
            failed += 1
            print(f"  ERROR: brotli failed with exit code {exc.returncode}")

            timing_rows.append(
                {
                    "PackageName": package_dir.name,
                    "Status": "failed",
                    "InputPath": str(package_dir),
                    "OutputPath": str(output_tar_br),
                    "OutputBytes": 0,
                    "ElapsedMilliseconds": 0.0,
                    "Quality": args.quality,
                    "Lgwin": lgwin if lgwin is not None else "",
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
                    "OutputPath": str(output_tar_br),
                    "OutputBytes": 0,
                    "ElapsedMilliseconds": 0.0,
                    "Quality": args.quality,
                    "Lgwin": lgwin if lgwin is not None else "",
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