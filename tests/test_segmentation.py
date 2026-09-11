import numpy as np
import pytest
from skimage.draw import disk

from microscopy.quantification import quantify_nuclei, summarize_nuclei
from microscopy.reference import (
    IlluminationFunctions,
    apply_illumination_correction,
    build_distance_compartments,
)
from microscopy.segmentation import segment_nuclei


def test_segments_and_measures_synthetic_nuclei() -> None:
    dna = np.zeros((128, 128), dtype=np.float32)
    gfp = np.full((128, 128), 8, dtype=np.float32)
    for center, dna_value, gfp_value in [
        ((36, 40), 180, 45),
        ((84, 88), 220, 125),
    ]:
        rr, cc = disk(center, 9, shape=dna.shape)
        dna[rr, cc] = dna_value
        gfp[rr, cc] = gfp_value

    labels = segment_nuclei(dna)
    nuclei = quantify_nuclei(labels, gfp)
    summary = summarize_nuclei(nuclei)

    assert labels.max() == 2
    assert summary["nucleus_count"] == 2
    measured = sorted(nuclei["mean_nuclear_gfp"])
    assert measured[0] == 45
    assert measured[1] > 115
    assert 80 < summary["median_nuclear_gfp"] < 90


def test_border_object_is_discarded() -> None:
    dna = np.zeros((96, 96), dtype=np.float32)
    rr, cc = disk((2, 40), 9, shape=dna.shape)
    dna[rr, cc] = 200
    rr, cc = disk((50, 50), 9, shape=dna.shape)
    dna[rr, cc] = 200

    assert segment_nuclei(dna).max() == 1


def test_reference_distance_compartments_produce_matched_ratios() -> None:
    labels = np.zeros((96, 96), dtype=np.int32)
    gfp = np.full((96, 96), 20, dtype=np.float32)
    for label, center, nuclear_value in [
        (1, (30, 30), 100),
        (2, (66, 66), 50),
    ]:
        rr, cc = disk(center, 8, shape=labels.shape)
        labels[rr, cc] = label
        gfp[rr, cc] = nuclear_value

    nuclei, cytoplasm = build_distance_compartments(labels)
    measured = quantify_nuclei(
        nuclei,
        gfp,
        cytoplasm_labels=cytoplasm,
    ).sort_values("label")
    summary = summarize_nuclei(measured)

    assert not np.any((nuclei > 0) & (cytoplasm > 0))
    assert set(np.unique(cytoplasm)) == {0, 1, 2}
    assert measured["mean_cytoplasmic_gfp"].tolist() == [20, 20]
    assert measured["cytoplasm_to_nucleus_ratio"].tolist() == [0.2, 0.4]
    assert summary["median_cytoplasm_to_nucleus_ratio"] == pytest.approx(0.3)


def test_reference_illumination_is_applied_by_division() -> None:
    image = np.array([[10, 20], [30, 40]], dtype=np.float32)
    illumination = IlluminationFunctions(
        gfp=np.array([[1, 2], [3, 4]], dtype=np.float32),
        dna=np.ones((2, 2), dtype=np.float32),
    )

    corrected = apply_illumination_correction(image, illumination.gfp)

    assert corrected.tolist() == [[10, 10], [10, 10]]
