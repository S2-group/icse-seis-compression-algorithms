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
DEFAULT_OUTPUT_DIR = "../data/zopfli_grid_search"
DEFAULT_ITERATIONS = "15,30,45,60,75,90,100,200"

OUTPUT_COLUMNS = [
    "PackageKey",
    "ConfigName",
    "Iterations",
    "Status",
    "InputDir",
    "UnpackedBytes",
    "OutputArchive",
    "ZopfliBytes",
    "ZopfliMB",
    "ElapsedMilliseconds",
    "Command",
    "Error",
]


def check_zopfli_available() -> None:
    if shutil.which("zopfli") is None:
        raise RuntimeError(
            "zopfli not found. Install it first, e.g. `sudo apt install zopfli` "
            "or `brew install zopfli`."
        )


def parse_iterations(value: str) -> List[int]:
    iterations = []

    for item in value.split(","):
        item = item.strip()

        if not item:
            continue

        number = int(item)

        if number <= 0:
            raise ValueError("zopfli iterations must be positive integers.")

        iterations.append(number)

    if not iterations:
        raise ValueError("No zopfli iteration values provided.")

    return iterations


def directory_size_bytes(path: Path) -> int:
    total = 0

    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size

    return total


def config_name(iterations: int) -> str:
    return f"zopfli_i{iterations}"


def config_csv_path(output_dir: Path, iterations: int) -> Path:
    return output_dir / f"{config_name(iterations)}_results.csv"


def config_archive_dir(output_dir: Path, iterations: int) -> Path:
    return output_dir / config_name(iterations) / "archives"


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


def build_zopfli_command(tar_path: Path, iterations: int) -> List[str]:
    return [
        "zopfli",
        f"--i{iterations}",
        str(tar_path),
    ]


def compress_with_zopfli(
    tar_path: Path,
    output_tgz: Path,
    iterations: int,
) -> List[str]:
    """
    zopfli creates <tar_path>.gz next to the input .tar.
    Then we move/rename it to output_tgz.
    """
    generated_gz = tar_path.with_suffix(tar_path.suffix + ".gz")

    if generated_gz.exists():
        generated_gz.unlink()

    if output_tgz.exists():
        output_tgz.unlink()

    cmd = build_zopfli_command(
        tar_path=tar_path,
        iterations=iterations,
    )

    subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    if not generated_gz.exists():
        raise RuntimeError(f"Expected zopfli output not found: {generated_gz}")

    shutil.move(str(generated_gz), str(output_tgz))

    return cmd


def measure_one(
    package_dir: Path,
    output_dir: Path,
    iterations: int,
    keep_archives: bool,
) -> Dict[str, object]:
    package_key = package_dir.name
    cfg_name = config_name(iterations)
    unpacked_bytes = directory_size_bytes(package_dir)

    archive_dir = config_archive_dir(output_dir, iterations)
    output_archive = archive_dir / f"{package_key}.tgz"

    if keep_archives:
        archive_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f"zopfli_grid_{package_key}_") as tmp:
        tmp_dir = Path(tmp)
        tar_path = tmp_dir / f"{package_key}.tar"

        if keep_archives:
            effective_output_archive = output_archive
        else:
            effective_output_archive = tmp_dir / f"{package_key}.tgz"

        start = time.perf_counter()
        command_text = ""

        try:
            create_uncompressed_tar(package_dir, tar_path)

            cmd = compress_with_zopfli(
                tar_path=tar_path,
                output_tgz=effective_output_archive,
                iterations=iterations,
            )

            elapsed_ms = (time.perf_counter() - start) * 1000
            zopfli_bytes = (
                effective_output_archive.stat().st_size
                if effective_output_archive.exists()
                else 0
            )

            command_text = " ".join(cmd)

            return {
                "PackageKey": package_key,
                "ConfigName": cfg_name,
                "Iterations": iterations,
                "Status": "success",
                "InputDir": str(package_dir),
                "UnpackedBytes": unpacked_bytes,
                "OutputArchive": str(output_archive if keep_archives else ""),
                "ZopfliBytes": zopfli_bytes,
                "ZopfliMB": zopfli_bytes / (1024 * 1024),
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
                "Iterations": iterations,
                "Status": "failed",
                "InputDir": str(package_dir),
                "UnpackedBytes": unpacked_bytes,
                "OutputArchive": str(output_archive if keep_archives else ""),
                "ZopfliBytes": "",
                "ZopfliMB": "",
                "ElapsedMilliseconds": elapsed_ms,
                "Command": command_text,
                "Error": f"zopfli failed with exit code {exc.returncode}: {stderr[:1000]}",
            }

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000

            return {
                "PackageKey": package_key,
                "ConfigName": cfg_name,
                "Iterations": iterations,
                "Status": "failed",
                "InputDir": str(package_dir),
                "UnpackedBytes": unpacked_bytes,
                "OutputArchive": str(output_archive if keep_archives else ""),
                "ZopfliBytes": "",
                "ZopfliMB": "",
                "ElapsedMilliseconds": elapsed_ms,
                "Command": command_text,
                "Error": str(exc),
            }


def print_config_summary(
    csv_path: Path,
    iterations: int,
    total_packages: int,
    done_successes: set[str],
) -> None:
    print("\nConfig")
    print("=" * 100)
    print(f"Config: {config_name(iterations)}")
    print(f"CSV: {csv_path}")
    print(f"Already completed successfully: {len(done_successes)}/{total_packages}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Grid search zopfli iteration counts for unpacked npm packages. "
            "Each zopfli configuration gets a dedicated CSV with size and timing."
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
        "--iterations",
        default=DEFAULT_ITERATIONS,
        help=(
            "Comma-separated zopfli iteration values to test. "
            f"Default: {DEFAULT_ITERATIONS}"
        ),
    )
    parser.add_argument(
        "--keep-archives",
        action="store_true",
        help=(
            "Keep the compressed .tgz archives. By default archives are created "
            "in a temporary directory and deleted after size/time are recorded."
        ),
    )
    parser.add_argument(
        "--only-config",
        default=None,
        help=(
            "Run only one config name, e.g. zopfli_i100. "
            "Useful for resuming a specific configuration."
        ),
    )

    args = parser.parse_args()

    check_zopfli_available()

    iterations_values = parse_iterations(args.iterations)

    if args.only_config:
        iterations_values = [
            iterations
            for iterations in iterations_values
            if config_name(iterations) == args.only_config
        ]

        if not iterations_values:
            raise ValueError(
                f"No config matched --only-config {args.only_config!r}. "
                "Example values: zopfli_i15, zopfli_i100, zopfli_i500"
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

    print("Zopfli grid search")
    print("=" * 100)
    print(f"Unpacked dir: {unpacked_dir}")
    print(f"Output dir: {output_dir}")
    print(f"Packages: {len(package_dirs)}")
    print(f"Iterations: {', '.join(str(i) for i in iterations_values)}")
    print(f"Keep archives: {args.keep_archives}")
    print(f"Configs: {', '.join(config_name(i) for i in iterations_values)}")

    global_start = time.perf_counter()

    for iterations in iterations_values:
        csv_path = config_csv_path(output_dir, iterations)
        ensure_csv(csv_path)

        done_successes = load_done_successes(csv_path)

        print_config_summary(
            csv_path=csv_path,
            iterations=iterations,
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
                f"iterations={iterations}"
            )

            row = measure_one(
                package_dir=package_dir,
                output_dir=output_dir,
                iterations=iterations,
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
                    f"  success: {row['ZopfliBytes']} bytes, "
                    f"{float(row['ElapsedMilliseconds']):.2f} ms"
                )
            else:
                failed += 1
                print(f"  failed: {row['Error']}")

        print("\nConfig summary")
        print("-" * 100)
        print(f"Config: {config_name(iterations)}")
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