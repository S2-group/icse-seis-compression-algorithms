#!/usr/bin/env python3

import argparse
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests


DEFAULT_INPUT_CSV = "../data/../data/top_2500_depended_enriched.csv"
DEFAULT_OUTPUT_DIR = "../data/npm_tarballs_2500"

REQUIRED_COLUMNS = [
    "PackageName",
    "DistTarball",
]


def safe_filename(package_name: str, tarball_url: str) -> str:
    """
    Produce a filesystem-safe filename.

    Examples:
      lodash -> lodash-4.17.21.tgz
      @types/node -> @types__node-20.0.0.tgz
    """
    parsed = urlparse(tarball_url)
    original_name = Path(parsed.path).name

    safe_package = package_name.replace("/", "__")
    safe_package = re.sub(r"[^A-Za-z0-9._@+-]+", "_", safe_package)

    if original_name.endswith(".tgz"):
        original_name = re.sub(r"[^A-Za-z0-9._@+-]+", "_", original_name)
        return f"{safe_package}--{original_name}"

    return f"{safe_package}.tgz"


def download_file(url: str, output_path: Path, timeout: int = 60, max_retries: int = 5) -> bool:
    if output_path.exists() and output_path.stat().st_size > 0:
        print(f"SKIP existing: {output_path.name}")
        return True

    for attempt in range(max_retries):
        try:
            with requests.get(url, stream=True, timeout=timeout) as response:
                if response.status_code == 429 or 500 <= response.status_code < 600:
                    sleep_for = min(60, 2 ** attempt)
                    print(f"RETRY {response.status_code}: sleeping {sleep_for}s")
                    time.sleep(sleep_for)
                    continue

                response.raise_for_status()

                tmp_path = output_path.with_suffix(output_path.suffix + ".part")

                with tmp_path.open("wb") as f:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)

                tmp_path.rename(output_path)
                print(f"DOWNLOADED: {output_path.name}")
                return True

        except requests.RequestException as exc:
            if attempt == max_retries - 1:
                print(f"ERROR downloading {url}: {exc}")
                return False

            sleep_for = min(60, 2 ** attempt)
            print(f"RETRY error: sleeping {sleep_for}s")
            time.sleep(sleep_for)

    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download npm tarballs for the top50 + random50 sample."
    )
    parser.add_argument(
        "input_csv",
        nargs="?",
        default=DEFAULT_INPUT_CSV,
        help=f"Input sample CSV. Default: {DEFAULT_INPUT_CSV}",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Existing output directory. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.1,
        help="Seconds to sleep between downloads. Default: 0.1",
    )

    args = parser.parse_args()

    input_csv = Path(args.input_csv)
    output_dir = Path(args.output_dir)

    if not output_dir.exists():
        raise FileNotFoundError(
            f"Output directory does not exist: {output_dir}\n"
            "Create it manually first, then rerun the script."
        )

    df = pd.read_csv(input_csv)

    for column in REQUIRED_COLUMNS:
        if column not in df.columns:
            raise ValueError(f"Missing required column: {column}")

    total = len(df)
    success = 0
    failed = 0
    skipped_missing_url = 0

    for index, row in df.iterrows():
        package_name = str(row["PackageName"]).strip()
        tarball_url = str(row["DistTarball"]).strip()

        if not package_name or not tarball_url or tarball_url.lower() == "nan":
            print(f"SKIP missing tarball URL: {package_name}")
            skipped_missing_url += 1
            continue

        filename = safe_filename(package_name, tarball_url)
        output_path = output_dir / filename

        print(f"[{index + 1}/{total}] {package_name}")

        ok = download_file(tarball_url, output_path)
        if ok:
            success += 1
        else:
            failed += 1

        time.sleep(args.sleep)

    print("\nSummary")
    print("=" * 80)
    print(f"Input rows: {total}")
    print(f"Downloaded or already present: {success}")
    print(f"Failed: {failed}")
    print(f"Skipped missing URL: {skipped_missing_url}")
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()