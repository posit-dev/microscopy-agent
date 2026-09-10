from pathlib import Path

import pytest

from microscopy.dataset import (
    build_well_metadata,
    normalize_well,
    parse_image_filename,
)


def _write_plate_map(path: Path, values: list[float]) -> None:
    path.write_text("DESCRIPTION test\n" + "\n".join(map(str, values)) + "\n")


def _fake_dataset(tmp_path: Path) -> Path:
    for index in range(1, 97):
        row = "ABCDEFGH"[(index - 1) // 12]
        column = (index - 1) % 12 + 1
        for channel in (1, 2):
            (tmp_path / f"Channel{channel}-{index:02d}-{row}-{column:02d}.BMP").touch()
    wortmannin = [0, 0, 0.98, 1.95, 3.91, 7.81, 15.63, 31.25, 62.5, 125, 250, 150] * 4
    ly294002 = [80, 0, 0.31, 0.63, 1.25, 2.5, 5, 10, 20, 40, 80, 0] * 4
    _write_plate_map(tmp_path / "BBBC013_v1_platemap_wortmannin.txt", wortmannin)
    _write_plate_map(tmp_path / "BBBC013_v1_platemap_ly294002.txt", ly294002)
    _write_plate_map(
        tmp_path / "BBBC013_v1_platemap_all.txt", wortmannin + ly294002
    )
    return tmp_path


@pytest.mark.parametrize(
    ("value", "expected"),
    [("a1", "A01"), (" A-01 ", "A01"), ("h12", "H12")],
)
def test_normalize_well(value: str, expected: str) -> None:
    assert normalize_well(value) == expected


def test_parse_image_filename() -> None:
    parsed = parse_image_filename("Channel2-62-F-02.BMP")
    assert parsed == {
        "channel": 2,
        "index": 62,
        "row": "F",
        "column": 2,
        "well": "F02",
    }


def test_build_metadata_pairs_channels_and_conditions(tmp_path: Path) -> None:
    metadata = build_well_metadata(_fake_dataset(tmp_path)).set_index("well")
    assert len(metadata) == 96
    assert metadata.loc["A03", "compound"] == "Wortmannin"
    assert metadata.loc["A03", "dose"] == pytest.approx(0.98)
    assert metadata.loc["E03", "compound"] == "LY294002"
    assert metadata.loc["E03", "dose"] == pytest.approx(0.31)
    assert metadata.loc["A02", "condition_type"] == "empty"
    assert metadata.loc["H12", "condition_type"] == "negative_control"
    assert metadata.loc["E01", "condition_type"] == "positive_control"
    assert metadata.loc["E01", "compound"] == "Wortmannin"
    assert metadata.loc["E01", "dose"] == 150
    assert metadata.loc["F02", "channel1_path"].endswith("Channel1-62-F-02.BMP")
    assert metadata.loc["F02", "channel2_path"].endswith("Channel2-62-F-02.BMP")


def test_duplicate_channel_is_rejected(tmp_path: Path) -> None:
    raw = _fake_dataset(tmp_path)
    duplicate_dir = raw / "duplicate"
    duplicate_dir.mkdir()
    (duplicate_dir / "Channel1-01-A-01.BMP").touch()
    with pytest.raises(ValueError, match="more than one Channel 1"):
        build_well_metadata(raw)
