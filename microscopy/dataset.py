"""BBBC013 file pairing and plate metadata."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

ROWS = "ABCDEFGH"
WELLS_PER_ROW = 12

_IMAGE_PATTERN = re.compile(
    r"^Channel(?P<channel>[12])-(?P<index>\d{2})-"
    r"(?P<row>[A-H])-(?P<column>\d{2})\.BMP$",
    re.IGNORECASE,
)
_WELL_PATTERN = re.compile(r"^(?P<row>[A-H])0?(?P<column>[1-9]|1[0-2])$")


def normalize_well(value: str) -> str:
    """Normalize a well identifier to A01-H12."""
    compact = re.sub(r"[\s_-]+", "", value).upper()
    match = _WELL_PATTERN.fullmatch(compact)
    if match is None:
        raise ValueError(f"Invalid well {value!r}; expected A01 through H12.")
    return f"{match.group('row')}{int(match.group('column')):02d}"


def parse_image_filename(path: str | Path) -> dict[str, Any]:
    """Parse one BBBC013 BMP filename."""
    name = Path(path).name
    match = _IMAGE_PATTERN.fullmatch(name)
    if match is None:
        raise ValueError(f"Unrecognized BBBC013 image filename: {name}")

    row = match.group("row").upper()
    column = int(match.group("column"))
    index = int(match.group("index"))
    expected_index = ROWS.index(row) * WELLS_PER_ROW + column
    if not 1 <= column <= WELLS_PER_ROW or index != expected_index:
        raise ValueError(
            f"Inconsistent well/index encoding in {name}: "
            f"expected {expected_index:02d}."
        )

    return {
        "channel": int(match.group("channel")),
        "index": index,
        "row": row,
        "column": column,
        "well": f"{row}{column:02d}",
    }


def _plate_values(path: Path, expected: int) -> list[float]:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing plate map {path}. Run scripts/download_data.py first."
        )
    lines = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    if not lines or not lines[0].startswith("DESCRIPTION"):
        raise ValueError(f"{path.name} does not start with a DESCRIPTION line.")
    values = [float(value) for value in lines[1:]]
    if len(values) != expected:
        raise ValueError(f"{path.name} has {len(values)} values; expected {expected}.")
    return values


def _image_pairs(raw_dir: Path) -> dict[str, dict[int, Path]]:
    pairs: dict[str, dict[int, Path]] = {}
    for path in sorted(raw_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() != ".bmp":
            continue
        parsed = parse_image_filename(path)
        channels = pairs.setdefault(parsed["well"], {})
        channel = parsed["channel"]
        if channel in channels:
            raise ValueError(
                f"Well {parsed['well']} has more than one Channel {channel} image."
            )
        channels[channel] = path.resolve()

    if len(pairs) != 96:
        raise ValueError(
            f"Found {len(pairs)} image wells under {raw_dir}; expected 96."
        )
    incomplete = sorted(
        well for well, channels in pairs.items() if set(channels) != {1, 2}
    )
    if incomplete:
        raise ValueError(f"Incomplete channel pairs: {', '.join(incomplete)}")
    return pairs


def _condition(row: str, column: int, mapped_dose: float) -> dict[str, Any]:
    if row in "ABCD":
        series_compound = "Wortmannin"
        replicate = "ABCD".index(row) + 1
        if column == 1:
            return {
                "condition_type": "negative_control",
                "compound": None,
                "dose": 0.0,
                "dose_unit": None,
                "series_compound": series_compound,
                "replicate": replicate,
                "condition_label": "Negative control",
            }
        if column == 2:
            return {
                "condition_type": "empty",
                "compound": None,
                "dose": None,
                "dose_unit": None,
                "series_compound": series_compound,
                "replicate": replicate,
                "condition_label": "Empty",
            }
        if column == 12:
            return {
                "condition_type": "positive_control",
                "compound": "Wortmannin",
                "dose": 150.0,
                "dose_unit": "nM",
                "series_compound": series_compound,
                "replicate": replicate,
                "condition_label": "Positive control: 150 nM Wortmannin",
            }
        return {
            "condition_type": "dose",
            "compound": series_compound,
            "dose": mapped_dose,
            "dose_unit": "nM",
            "series_compound": series_compound,
            "replicate": replicate,
            "condition_label": f"{mapped_dose:g} nM Wortmannin",
        }

    series_compound = "LY294002"
    replicate = "EFGH".index(row) + 1
    if column == 1:
        # Broad's documentation and corrected CellProfiler metadata identify
        # this shared control as 150 nM Wortmannin. The LY plate-map file alone
        # contains 80 here because it encodes the LY series' numeric layout.
        return {
            "condition_type": "positive_control",
            "compound": "Wortmannin",
            "dose": 150.0,
            "dose_unit": "nM",
            "series_compound": series_compound,
            "replicate": replicate,
            "condition_label": "Positive control: 150 nM Wortmannin",
        }
    if column == 2:
        return {
            "condition_type": "empty",
            "compound": None,
            "dose": None,
            "dose_unit": None,
            "series_compound": series_compound,
            "replicate": replicate,
            "condition_label": "Empty",
        }
    if column == 12:
        return {
            "condition_type": "negative_control",
            "compound": None,
            "dose": 0.0,
            "dose_unit": None,
            "series_compound": series_compound,
            "replicate": replicate,
            "condition_label": "Negative control",
        }
    return {
        "condition_type": "dose",
        "compound": series_compound,
        "dose": mapped_dose,
        "dose_unit": "µM",
        "series_compound": series_compound,
        "replicate": replicate,
        "condition_label": f"{mapped_dose:g} µM LY294002",
    }


def build_well_metadata(raw_dir: str | Path) -> pd.DataFrame:
    """Build the canonical one-row-per-well metadata table."""
    raw = Path(raw_dir)
    pairs = _image_pairs(raw)
    all_values = _plate_values(raw / "BBBC013_v1_platemap_all.txt", 96)
    wortmannin_values = _plate_values(
        raw / "BBBC013_v1_platemap_wortmannin.txt", 48
    )
    ly_values = _plate_values(raw / "BBBC013_v1_platemap_ly294002.txt", 48)
    if all_values[:48] != wortmannin_values or all_values[48:] != ly_values:
        raise ValueError("The compound-specific plate maps disagree with the full map.")

    records: list[dict[str, Any]] = []
    for row_index, row in enumerate(ROWS):
        for column in range(1, WELLS_PER_ROW + 1):
            position = row_index * WELLS_PER_ROW + column - 1
            well = f"{row}{column:02d}"
            mapped_dose = all_values[position]
            records.append(
                {
                    "well": well,
                    "row": row,
                    "column": column,
                    "channel1_path": str(pairs[well][1]),
                    "channel2_path": str(pairs[well][2]),
                    "plate_map_dose": mapped_dose,
                    **_condition(row, column, mapped_dose),
                }
            )

    return pd.DataFrame.from_records(records).sort_values(
        ["row", "column"], ignore_index=True
    )
