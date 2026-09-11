"""Reference-derived BBBC013 illumination and compartment construction."""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from scipy.io import loadmat
from skimage import measure
from skimage.segmentation import expand_labels


@dataclass(frozen=True)
class IlluminationFunctions:
    """Per-channel illumination functions from the Broad reference archive."""

    gfp: np.ndarray
    dna: np.ndarray


@dataclass(frozen=True)
class CompartmentConfig:
    """Geometry copied from the published BioImage CellProfiler pipelines."""

    nucleus_shrink: int = 1
    cell_expansion: int = 6
    cytoplasm_shrink: int = 1


REFERENCE_COMPARTMENT_CONFIG = CompartmentConfig()

_GFP_ILLUMINATION_MEMBER = "Bioimage/Ch1_IllumFunction.mat"
_DNA_ILLUMINATION_MEMBER = "Bioimage/Ch2_IllumFunction.mat"


def _mat_image(contents: bytes, *, member: str) -> np.ndarray:
    payload = loadmat(io.BytesIO(contents))
    if "Image" not in payload:
        raise ValueError(f"{member} does not contain a MATLAB Image array.")
    image = np.asarray(payload["Image"], dtype=np.float32)
    if image.ndim != 2 or not np.all(np.isfinite(image)) or np.any(image <= 0):
        raise ValueError(f"{member} is not a positive finite 2D illumination image.")
    return image


@lru_cache(maxsize=4)
def load_reference_illumination(
    archive_path: str | Path,
) -> IlluminationFunctions:
    """Load the published GFP and DNA illumination functions."""
    path = Path(archive_path)
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing reference archive {path}. Run "
            "`python scripts/download_data.py`."
        )
    with zipfile.ZipFile(path) as archive:
        try:
            gfp = _mat_image(
                archive.read(_GFP_ILLUMINATION_MEMBER),
                member=_GFP_ILLUMINATION_MEMBER,
            )
            dna = _mat_image(
                archive.read(_DNA_ILLUMINATION_MEMBER),
                member=_DNA_ILLUMINATION_MEMBER,
            )
        except KeyError as error:
            raise ValueError(
                f"{path.name} is missing a published illumination function."
            ) from error
    if gfp.shape != dna.shape:
        raise ValueError(
            "The GFP and DNA illumination functions have different shapes."
        )
    return IlluminationFunctions(gfp=gfp, dna=dna)


def apply_illumination_correction(
    image: np.ndarray,
    illumination: np.ndarray,
) -> np.ndarray:
    """Apply the reference pipeline's divide illumination correction."""
    if image.shape != illumination.shape:
        raise ValueError(
            "Image and illumination function must have identical dimensions."
        )
    return image.astype(np.float32) / illumination.astype(np.float32)


def shrink_labels(labels: np.ndarray, pixels: int) -> np.ndarray:
    """Shrink each labeled object inward by a fixed number of pixels."""
    if pixels < 0:
        raise ValueError("Shrink distance cannot be negative.")
    if pixels == 0:
        return labels.copy()

    shrunk = np.zeros_like(labels)
    padding = pixels + 1
    for region in measure.regionprops(labels):
        min_row, min_col, max_row, max_col = region.bbox
        object_mask = labels[min_row:max_row, min_col:max_col] == region.label
        padded = np.pad(object_mask, padding)
        distance = ndi.distance_transform_edt(padded)
        retained = distance > pixels
        retained = retained[
            padding:-padding,
            padding:-padding,
        ]
        target = shrunk[min_row:max_row, min_col:max_col]
        target[retained] = region.label
    return shrunk


def build_distance_compartments(
    original_nuclei: np.ndarray,
    config: CompartmentConfig = REFERENCE_COMPARTMENT_CONFIG,
) -> tuple[np.ndarray, np.ndarray]:
    """Build the published distance-based nucleus and cytoplasm compartments."""
    if original_nuclei.ndim != 2:
        raise ValueError("Nuclear labels must be a two-dimensional array.")

    nuclei = shrink_labels(original_nuclei, config.nucleus_shrink)
    cells = expand_labels(original_nuclei, distance=config.cell_expansion)
    original_cytoplasm = np.where(original_nuclei == 0, cells, 0)
    cytoplasm = shrink_labels(original_cytoplasm, config.cytoplasm_shrink)
    return nuclei, cytoplasm
