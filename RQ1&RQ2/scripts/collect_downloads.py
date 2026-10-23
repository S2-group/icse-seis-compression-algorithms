#!/usr/bin/env python3

import argparse
import csv
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote

import requests


DEFAULT_INPUT_CSV = "../data/top_2500_depended.csv"
DEFAULT_OUTPUT_CSV = "../data/top_2500_depended_enriched.csv"
DEFAULT_PACKAGE_COLUMN = "PackageName"
DEFAULT_BATCH_SIZE = 50

DOWNLOAD_RANGES = {
    "last-week": "DownloadsLastWeek",
    "last-month": "DownloadsLastMonth",
    "last-year": "DownloadsLastYear",
}

DOWNLOAD_API_URL = "https://api.npmjs.org/downloads/point/{period}/{packages}"
REGISTRY_PACKAGE_URL = "https://registry.npmjs.org/{package}"
REGISTRY_LATEST_URL = "https://registry.npmjs.org/{package}/latest"


OUTPUT_COLUMNS = [
    "PackageName",
    "NDependents",
    "DownloadsLastWeek",
    "DownloadsLastMonth",
    "DownloadsLastYear",
    "LatestVersion",
    "LatestPublishedAt",
    "ModifiedAt",
    "Description",
    "License",
    "RepositoryUrl",
    "Homepage",
    "Deprecated",
    "MaintainersCount",
    "DependenciesCount",
    "PeerDependenciesCount",
    "OptionalDependenciesCount",
    "NodeEngine",
    "HasTypes",
    "BinCount",
    "DistTarball",
]


def chunks(items: List[str], size: int) -> Iterable[List[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def normalize_package_name(name: str) -> str:
    return name.strip()


def encode_package_for_url(package_name: str) -> str:
    # Scoped package: @scope/name -> %40scope%2Fname
    return quote(package_name, safe="")


def is_scoped_package(package_name: str) -> bool:
    return package_name.startswith("@") and "/" in package_name


def request_json(
    url: str,
    *,
    max_retries: int = 5,
    timeout: int = 30,
    headers: Optional[Dict[str, str]] = None,
) -> Optional[Any]:
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=timeout, headers=headers)

            if response.status_code == 404:
                return None

            if response.status_code == 400:
                print(f"ERROR 400 Bad Request: {url}")
                print(response.text[:500])
                return None

            if response.status_code == 429 or 500 <= response.status_code < 600:
                sleep_for = min(60, 2 ** attempt)
                time.sleep(sleep_for)
                continue

            response.raise_for_status()
            return response.json()

        except requests.RequestException as exc:
            if attempt == max_retries - 1:
                print(f"ERROR: failed request: {url} ({exc})")
                return None

            sleep_for = min(60, 2 ** attempt)
            time.sleep(sleep_for)

    return None


def fetch_downloads_for_batch(
    packages: List[str],
    period: str,
) -> Dict[str, Optional[int]]:
    # Bulk endpoint does not support scoped packages.
    scoped_packages = [p for p in packages if is_scoped_package(p)]
    unscoped_packages = [p for p in packages if not is_scoped_package(p)]

    results: Dict[str, Optional[int]] = {}

    if unscoped_packages:
        encoded_packages = [
            encode_package_for_url(package_name)
            for package_name in unscoped_packages
        ]
        package_expr = ",".join(encoded_packages)

        url = DOWNLOAD_API_URL.format(period=period, packages=package_expr)

        data = request_json(url)
        if data is None:
            for package_name in unscoped_packages:
                results[package_name] = None
        elif isinstance(data, dict) and "downloads" in data and "package" in data:
            results[data["package"]] = data.get("downloads")
        elif isinstance(data, dict):
            for package_name in unscoped_packages:
                package_data = data.get(package_name)
                if isinstance(package_data, dict):
                    results[package_name] = package_data.get("downloads")
                else:
                    results[package_name] = None

    for package_name in scoped_packages:
        results[package_name] = fetch_downloads_single(package_name, period)
        time.sleep(0.1)

    return results



def fetch_downloads_single(
    package_name: str,
    period: str,
) -> Optional[int]:
    encoded_package = encode_package_for_url(package_name)
    url = DOWNLOAD_API_URL.format(period=period, packages=encoded_package)

    data = request_json(url)
    if not isinstance(data, dict):
        return None

    return data.get("downloads")


def fetch_downloads(
    packages: List[str],
    period: str,
    batch_size: int,
) -> Dict[str, Optional[int]]:
    all_results: Dict[str, Optional[int]] = {}

    unscoped_packages = [p for p in packages if not is_scoped_package(p)]
    scoped_packages = [p for p in packages if is_scoped_package(p)]

    total_batches = (len(unscoped_packages) + batch_size - 1) // batch_size

    for index, batch in enumerate(chunks(unscoped_packages, batch_size), start=1):
        print(f"[downloads:{period}] unscoped batch {index}/{total_batches}")
        all_results.update(fetch_downloads_for_batch(batch, period))
        time.sleep(0.2)

    for index, package_name in enumerate(scoped_packages, start=1):
        print(f"[downloads:{period}] scoped {index}/{len(scoped_packages)} {package_name}")
        all_results[package_name] = fetch_downloads_single(package_name, period)
        time.sleep(0.1)

    return all_results


def extract_repository_url(repository: Any) -> str:
    if isinstance(repository, str):
        return repository

    if isinstance(repository, dict):
        return repository.get("url", "") or ""

    return ""


def extract_license(manifest: Dict[str, Any]) -> str:
    license_value = manifest.get("license")

    if isinstance(license_value, str):
        return license_value

    if isinstance(license_value, dict):
        return license_value.get("type", "") or license_value.get("name", "") or ""

    licenses = manifest.get("licenses")
    if isinstance(licenses, list):
        extracted = []
        for item in licenses:
            if isinstance(item, str):
                extracted.append(item)
            elif isinstance(item, dict):
                value = item.get("type") or item.get("name")
                if value:
                    extracted.append(value)
        return ";".join(extracted)

    return ""


def count_mapping(value: Any) -> int:
    return len(value) if isinstance(value, dict) else 0


def count_bin(value: Any) -> int:
    if isinstance(value, dict):
        return len(value)
    if isinstance(value, str):
        return 1
    return 0


def has_types(manifest: Dict[str, Any]) -> bool:
    if manifest.get("types") or manifest.get("typings"):
        return True

    files = manifest.get("files")
    if isinstance(files, list):
        for item in files:
            if isinstance(item, str) and item.endswith((".d.ts", ".d.mts", ".d.cts")):
                return True

    return False


def latest_published_at(packument: Dict[str, Any], latest_version: str) -> str:
    times = packument.get("time")
    if isinstance(times, dict):
        return times.get(latest_version, "") or ""
    return ""


def modified_at(packument: Dict[str, Any]) -> str:
    times = packument.get("time")
    if isinstance(times, dict):
        return times.get("modified", "") or ""
    return ""


def fetch_registry_metadata(package_name: str) -> Dict[str, Any]:
    encoded = encode_package_for_url(package_name)

    packument_url = REGISTRY_PACKAGE_URL.format(package=encoded)
    latest_url = REGISTRY_LATEST_URL.format(package=encoded)

    # Full packument is needed for time.modified and latest publish timestamp.
    packument = request_json(packument_url)
    latest_manifest = request_json(
        latest_url,
        headers={"Accept": "application/json"},
    )

    if not isinstance(packument, dict):
        packument = {}

    if not isinstance(latest_manifest, dict):
        latest_manifest = {}

    dist_tags = packument.get("dist-tags") if isinstance(packument.get("dist-tags"), dict) else {}
    latest_version = (
        latest_manifest.get("version")
        or dist_tags.get("latest")
        or ""
    )

    description = (
        latest_manifest.get("description")
        or packument.get("description")
        or ""
    )

    deprecated = latest_manifest.get("deprecated", "")
    if deprecated is True:
        deprecated = "true"
    elif deprecated is False or deprecated is None:
        deprecated = ""
    else:
        deprecated = str(deprecated)

    maintainers = packument.get("maintainers")
    maintainers_count = len(maintainers) if isinstance(maintainers, list) else 0

    engines = latest_manifest.get("engines")
    node_engine = ""
    if isinstance(engines, dict):
        node_engine = engines.get("node", "") or ""

    dist = latest_manifest.get("dist")
    dist_tarball = ""
    if isinstance(dist, dict):
        dist_tarball = dist.get("tarball", "") or ""

    return {
        "LatestVersion": latest_version,
        "LatestPublishedAt": latest_published_at(packument, latest_version),
        "ModifiedAt": modified_at(packument),
        "Description": description,
        "License": extract_license(latest_manifest),
        "RepositoryUrl": extract_repository_url(latest_manifest.get("repository")),
        "Homepage": latest_manifest.get("homepage", "") or "",
        "Deprecated": deprecated,
        "MaintainersCount": maintainers_count,
        "DependenciesCount": count_mapping(latest_manifest.get("dependencies")),
        "PeerDependenciesCount": count_mapping(latest_manifest.get("peerDependencies")),
        "OptionalDependenciesCount": count_mapping(latest_manifest.get("optionalDependencies")),
        "NodeEngine": node_engine,
        "HasTypes": str(has_types(latest_manifest)).lower(),
        "BinCount": count_bin(latest_manifest.get("bin")),
        "DistTarball": dist_tarball,
    }


def fetch_all_registry_metadata(packages: List[str]) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}

    for index, package_name in enumerate(packages, start=1):
        print(f"[registry] {index}/{len(packages)} {package_name}")
        results[package_name] = fetch_registry_metadata(package_name)
        time.sleep(0.1)

    return results


def read_csv(input_path: Path) -> List[Dict[str, str]]:
    with input_path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(output_path: Path, rows: List[Dict[str, Any]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enrich top npm packages CSV with downloads and npm registry metadata."
    )
    parser.add_argument(
        "input_csv",
        nargs="?",
        default=DEFAULT_INPUT_CSV,
        help=f"Input CSV. Default: {DEFAULT_INPUT_CSV}",
    )
    parser.add_argument(
        "-o",
        "--output-csv",
        default=DEFAULT_OUTPUT_CSV,
        help=f"Output CSV. Default: {DEFAULT_OUTPUT_CSV}",
    )
    parser.add_argument(
        "--package-column",
        default=DEFAULT_PACKAGE_COLUMN,
        help=f"Package column name. Default: {DEFAULT_PACKAGE_COLUMN}",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Downloads API batch size. Default: {DEFAULT_BATCH_SIZE}",
    )

    args = parser.parse_args()

    input_path = Path(args.input_csv)
    output_path = Path(args.output_csv)

    rows = read_csv(input_path)
    if not rows:
        raise ValueError("Input CSV is empty.")

    if args.package_column not in rows[0]:
        available = ", ".join(rows[0].keys())
        raise ValueError(
            f"Column '{args.package_column}' not found. Available columns: {available}"
        )

    packages: List[str] = []
    seen = set()

    for row in rows:
        package_name = normalize_package_name(row[args.package_column])
        row["PackageName"] = package_name

        if package_name and package_name not in seen:
            packages.append(package_name)
            seen.add(package_name)

    print(f"Found {len(packages)} unique packages.")

    downloads_by_period: Dict[str, Dict[str, Optional[int]]] = {}

    for period in DOWNLOAD_RANGES:
        downloads_by_period[period] = fetch_downloads(
            packages,
            period,
            batch_size=args.batch_size,
        )

    metadata_by_package = fetch_all_registry_metadata(packages)

    enriched_rows: List[Dict[str, Any]] = []

    for row in rows:
        package_name = row["PackageName"]

        enriched: Dict[str, Any] = {
            "PackageName": package_name,
            "NDependents": row.get("NDependents", ""),
        }

        for period, column_name in DOWNLOAD_RANGES.items():
            value = downloads_by_period[period].get(package_name)
            enriched[column_name] = "" if value is None else value

        enriched.update(metadata_by_package.get(package_name, {}))

        enriched_rows.append(enriched)

    write_csv(output_path, enriched_rows)

    print(f"Done. Wrote: {output_path}")


if __name__ == "__main__":
    main()