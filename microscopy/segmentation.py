"""Deterministic classical nucleus segmentation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from skimage import filters, measure, morphology, segmentation


@dataclass(frozen=True)
class SegmentationConfig:
    """Fixed parameters for the trusted demonstration workflow."""

    gaussian_sigma: float = 1.0
    minimum_area: int = 40
    maximum_area: int = 1_200
    maximum_hole_area: int = 32
    clear_border_objects: bool = True


DEFAULT_CONFIG = SegmentationConfig()


def segment_nuclei(
    dna_image: np.ndarray,
    config: SegmentationConfig = DEFAULT_CONFIG,
) -> np.ndarray:
    """Segment bright nuclei from an 8-bit DNA image."""
    if dna_image.ndim != 2:
        raise ValueError("DNA image must be a two-dimensional grayscale array.")

    smoothed = filters.gaussian(
        dna_image.astype(np.float32),
        sigma=config.gaussian_sigma,
        preserve_range=True,
    )
    threshold = filters.threshold_otsu(smoothed)
    mask = smoothed > threshold
    mask = morphology.remove_small_objects(
        mask, max_size=config.minimum_area - 1
    )
    mask = morphology.remove_small_holes(
        mask, max_size=config.maximum_hole_area
    )
    mask = morphology.opening(mask, morphology.disk(1))
    if config.clear_border_objects:
        mask = segmentation.clear_border(mask)

    labels = measure.label(mask)
    for region in measure.regionprops(labels):
        if region.area < config.minimum_area or region.area > config.maximum_area:
            labels[labels == region.label] = 0
    return measure.label(labels > 0)
