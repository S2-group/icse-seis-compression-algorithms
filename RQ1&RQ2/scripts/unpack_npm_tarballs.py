#!/usr/bin/env python3

import argparse
import shutil
import tarfile
import tempfile
from pathlib import Path


DEFAULT_TARBALL_DIR = "../data/npm_tarballs_2500"
DEFAULT_UNPACKED_DIR = "../data/unpacked_2500"


def package_dir_name(tarball_path: Path) -> str:
    name = tarball_path.name

    if name.endswith(".tgz"):
        name = name[:-4]
    elif name.endswith(".tar.gz"):
        name = name[:-7]

    return name


def is_safe_tar_member(base_dir: Path, member_path: Path) -> bool:
    try:
        base_dir_resolved = base_dir.resolve()
        member_path_resolved = member_path.resolve()
        return member_path_resolved.is_relative_to(base_dir_resolved)
    except AttributeError:
        base_dir_resolved = base_dir.resolve()
        member_path_resolved = member_path.resolve()
        return str(member_path_resolved).startswith(str(base_dir_resolved))


def safe_extract_tarball(tarball_path: Path, destination: Path) -> None:
    with tarfile.open(tarball_path, "r:gz") as tar:
        for member in tar.getmembers():
            target_path = destination / member.name

            if not is_safe_tar_member(destination, target_path):
                raise RuntimeError(
                    f"Unsafe path detected in tarball {tarball_path}: {member.name}"
                )

        tar.extractall(destination)


def move_contents(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)

    for item in src.iterdir():
        target = dst / item.name

        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()

        shutil.move(str(item), str(target))


def unpack_one(tarball_path: Path, unpacked_dir: Path, overwrite: bool) -> str:
    output_dir = unpacked_dir / package_dir_name(tarball_path)

    if output_dir.exists():
        if overwrite:
            shutil.rmtree(output_dir)
        else:
            return "skipped_existing"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        safe_extract_tarball(tarball_path, tmp_dir)

        npm_package_dir = tmp_dir / "package"

        if npm_package_dir.exists() and npm_package_dir.is_dir():
            move_contents(npm_package_dir, output_dir)
        else:
            output_dir.mkdir(parents=True, exist_ok=True)
            move_contents(tmp_dir, output_dir)

    return "unpacked"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Unpack npm .tgz packages into one folder per package."
    )
    parser.add_argument(
        "--tarball-dir",
        default=DEFAULT_TARBALL_DIR,
        help=f"Directory containing downloaded .tgz files. Default: {DEFAULT_TARBALL_DIR}",
    )
    parser.add_argument(
        "--unpacked-dir",
        default=DEFAULT_UNPACKED_DIR,
        help=f"Directory where packages will be unpacked. Default: {DEFAULT_UNPACKED_DIR}",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite already unpacked package folders.",
    )

    args = parser.parse_args()

    tarball_dir = Path(args.tarball_dir)
    unpacked_dir = Path(args.unpacked_dir)

    if not tarball_dir.exists():
        raise FileNotFoundError(f"Tarball directory does not exist: {tarball_dir}")

    unpacked_dir.mkdir(parents=True, exist_ok=True)

    tarballs = sorted(tarball_dir.glob("*.tgz"))

    if not tarballs:
        print(f"No .tgz files found in: {tarball_dir}")
        return

    unpacked = 0
    skipped_existing = 0
    failed = 0

    for index, tarball_path in enumerate(tarballs, start=1):
        print(f"[{index}/{len(tarballs)}] {tarball_path.name}")

        try:
            status = unpack_one(
                tarball_path=tarball_path,
                unpacked_dir=unpacked_dir,
                overwrite=args.overwrite,
            )

            if status == "unpacked":
                unpacked += 1
                print("  unpacked")
            elif status == "skipped_existing":
                skipped_existing += 1
                print("  skipped existing")

        except Exception as exc:
            failed += 1
            print(f"  ERROR: {exc}")

    print("\nSummary")
    print("=" * 80)
    print(f"Tarballs found: {len(tarballs)}")
    print(f"Unpacked: {unpacked}")
    print(f"Skipped existing: {skipped_existing}")
    print(f"Failed: {failed}")
    print(f"Output directory: {unpacked_dir}")


if __name__ == "__main__":
    main()