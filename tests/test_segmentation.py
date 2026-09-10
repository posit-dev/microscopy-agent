import numpy as np
from skimage.draw import disk

from microscopy.quantification import quantify_nuclei, summarize_nuclei
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
