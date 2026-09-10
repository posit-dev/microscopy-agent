from __future__ import annotations

import base64
from pathlib import Path

import commons
import numpy as np
import pytest
from PIL import Image
from skimage.draw import disk

from measures import uploads as upload_measures
from microscopy.uploads import UploadLibrary, fetch_upload


def _channel_pair(directory: Path) -> tuple[Path, Path]:
    dna = np.zeros((128, 128), dtype=np.uint8)
    gfp = np.full((128, 128), 8, dtype=np.uint8)
    for center, radius, dna_value, gfp_value in [
        ((38, 42), 6, 180, 45),
        ((86, 84), 11, 220, 125),
    ]:
        rr, cc = disk(center, radius, shape=dna.shape)
        dna[rr, cc] = dna_value
        gfp[rr, cc] = gfp_value

    gfp_path = directory / "sample-gfp.png"
    dna_path = directory / "sample-dna.png"
    Image.fromarray(gfp).save(gfp_path)
    Image.fromarray(dna).save(dna_path)
    return gfp_path, dna_path


def test_upload_library_persists_files_and_inventory(tmp_path: Path) -> None:
    gfp_path, dna_path = _channel_pair(tmp_path)
    root = tmp_path / "library"
    library = UploadLibrary(root)

    sample = library.register_pair(
        sample_name="Synthetic sample",
        gfp_path=gfp_path,
        dna_path=dna_path,
    )

    reopened = UploadLibrary(root)
    assert reopened.list_samples() == [sample]
    resolved = fetch_upload(reopened.engine, sample.upload_id)
    assert Path(resolved["gfp_path"]).is_file()
    assert Path(resolved["dna_path"]).is_file()
    assert "Synthetic sample" in reopened.prompt_inventory()
    assert str(root) not in reopened.prompt_inventory()


def test_upload_library_rejects_mismatched_channels(tmp_path: Path) -> None:
    gfp_path, dna_path = _channel_pair(tmp_path)
    Image.fromarray(np.zeros((64, 64), dtype=np.uint8)).save(dna_path)
    library = UploadLibrary(tmp_path / "library")

    with pytest.raises(ValueError, match="identical pixel dimensions"):
        library.register_pair(
            sample_name="Mismatch",
            gfp_path=gfp_path,
            dna_path=dna_path,
        )


def test_uploaded_measure_varies_runtime_analysis_parameters(tmp_path: Path) -> None:
    gfp_path, dna_path = _channel_pair(tmp_path)
    library = UploadLibrary(tmp_path / "library")
    sample = library.register_pair(
        sample_name="Parameter test",
        gfp_path=gfp_path,
        dna_path=dna_path,
    )

    permissive = upload_measures.analyze_uploaded_sample(
        sample.upload_id,
        minimum_area=40,
        uploads=library.engine,
    )
    restrictive = upload_measures.analyze_uploaded_sample(
        sample.upload_id,
        channel="dna",
        minimum_area=150,
        uploads=library.engine,
    )

    assert "Segmented nuclei: 2" in permissive.value
    assert "Segmented nuclei: 1" in restrictive.value
    assert base64.b64decode(permissive.image_base64).startswith(b"\x89PNG")
    assert permissive.image_base64 != restrictive.image_base64


def test_upload_engine_is_injected_but_not_model_visible() -> None:
    layer = commons.semantic_layer(upload_measures)
    measure = layer.measures["analyze_uploaded_sample"]

    assert measure.injected == ("uploads",)
    assert "uploads" not in measure.params.model_json_schema()["properties"]
