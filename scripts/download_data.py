#!/usr/bin/env python3
"""Download and validate BBBC013 v1."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
RAW_DIR = PROJECT_ROOT / "data" / "raw"
BASE_URL = "https://data.broadinstitute.org/bbbc/BBBC013"

FILES = {
    "BBBC013_v1_images_bmp.zip": (
        f"{BASE_URL}/BBBC013_v1_images_bmp.zip",
        "c059b569d96f70ad5626fad144867e6ece4353622119c46a8af8f9794f1e7985",
    ),
    "BBBC013_v1_platemap_all.txt": (
        f"{BASE_URL}/BBBC013_v1_platemap_all.txt",
        "e8db6666271d47962fa7d2abfa3ea965352b8e87bee461f2983d0f667bc7ff08",
    ),
    "BBBC013_v1_platemap_wortmannin.txt": (
        f"{BASE_URL}/BBBC013_v1_platemap_wortmannin.txt",
        "c833784cb9f797562c07b3c5d21b03739fb88436ff31847d408528aebf00f59b",
    ),
    "BBBC013_v1_platemap_ly294002.txt": (
        f"{BASE_URL}/BBBC013_v1_platemap_ly294002.txt",
        "1dcdee3cd49ab7c5b4f6fc9fbe3e10034df3aa3cbae6c83c25a5b457aabf6834",
    ),
    "visual_plate_map.png": (
        f"{BASE_URL}/visual_plate_map.png",
        "e243a7d9b8ac1fba58b84ca26517119427c7ce88cfc471ee971601b5bdc0dec8",
    ),
}
REFERENCE = {
    "BBBC013_reproduce_logan.zip": (
        f"{BASE_URL}/BBBC013_reproduce_logan.zip",
        "5ab59bbaddf75fee08436d2d7cfc7460ebfdaa6fdf1b8adb71274c7c27f885f3",
    )
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(name: str, url: str, expected: str, force: bool) -> Path:
    destination = RAW_DIR / name
    if destination.exists() and not force and sha256(destination) == expected:
        print(f"Using validated {name}")
        return destination

    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.unlink(missing_ok=True)
    print(f"Downloading {name}")
    with urllib.request.urlopen(url) as response, temporary.open("wb") as output:
        shutil.copyfileobj(response, output)
    actual = sha256(temporary)
    if actual != expected:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            f"Checksum mismatch for {name}: expected {expected}, got {actual}."
        )
    temporary.replace(destination)
    return destination


def safe_extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            target = (destination / member.filename).resolve()
            if root not in target.parents and target != root:
                raise RuntimeError(f"Unsafe ZIP member: {member.filename}")
        bundle.extractall(destination)


def validate_images() -> None:
    from microscopy.dataset import parse_image_filename

    images = [
        path
        for path in RAW_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() == ".bmp"
    ]
    if len(images) != 192:
        raise RuntimeError(f"Found {len(images)} BMP files; expected 192.")
    pairs: dict[str, set[int]] = {}
    for image in images:
        parsed = parse_image_filename(image)
        channels = pairs.setdefault(parsed["well"], set())
        if parsed["channel"] in channels:
            raise RuntimeError(
                f"Duplicate Channel {parsed['channel']} image for {parsed['well']}."
            )
        channels.add(parsed["channel"])
    incomplete = [well for well, channels in pairs.items() if channels != {1, 2}]
    if len(pairs) != 96 or incomplete:
        raise RuntimeError(
            f"Expected 96 complete image pairs; got {len(pairs)} with "
            f"{len(incomplete)} incomplete."
        )
    print("Validated 192 BMP files: 96 complete Channel 1/Channel 2 pairs")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--with-reference",
        action="store_true",
        help=(
            "Retained for compatibility; the reference archive is now downloaded "
            "by default because the trusted workflow uses its illumination maps."
        ),
    )
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    selected = dict(FILES)
    selected.update(REFERENCE)

    paths = {
        name: download(name, url, expected, args.force)
        for name, (url, expected) in selected.items()
    }
    image_dir = RAW_DIR / "images"
    needs_extraction = args.force or not image_dir.exists()
    if not needs_extraction:
        try:
            validate_images()
        except RuntimeError as error:
            print(f"Existing extraction is incomplete ({error}); rebuilding it.")
            needs_extraction = True

    if needs_extraction:
        if image_dir.exists():
            shutil.rmtree(image_dir)
        print("Extracting image archive")
        safe_extract(paths["BBBC013_v1_images_bmp.zip"], image_dir)
        validate_images()
    print("SHA-256 checksums:")
    for name, path in paths.items():
        print(f"  {sha256(path)}  {name}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        raise
