"""Composition of loading, segmentation, and quantification."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from PIL import Image

from .quantification import quantify_nuclei, summarize_nuclei
from .reference import (
    REFERENCE_COMPARTMENT_CONFIG,
    CompartmentConfig,
    IlluminationFunctions,
    apply_illumination_correction,
    build_distance_compartments,
    load_reference_illumination,
)
from .segmentation import DEFAULT_CONFIG, SegmentationConfig, segment_nuclei

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ARCHIVE_PATH = PROJECT_ROOT / "data" / "raw" / "BBBC013_reproduce_logan.zip"
ANALYSIS_VERSION = "nuclear-cytoplasm-gfp-v2"


@dataclass
class WellAnalysis:
    """All trusted outputs for one well."""

    metadata: dict[str, Any]
    gfp_image: np.ndarray
    dna_image: np.ndarray
    corrected_gfp_image: np.ndarray
    corrected_dna_image: np.ndarray
    labels: np.ndarray
    cytoplasm_labels: np.ndarray | None
    nuclei: pd.DataFrame
    summary: dict[str, float | int]


def load_grayscale(path: str | Path) -> np.ndarray:
    """Load an image as float32 while preserving 8-bit intensity units."""
    with Image.open(path) as image:
        return np.asarray(image.convert("L"), dtype=np.float32)


def analyze_well(
    metadata: Mapping[str, Any] | pd.Series,
    config: SegmentationConfig = DEFAULT_CONFIG,
) -> WellAnalysis:
    """Run the fixed analysis pipeline for one metadata row."""
    record = dict(metadata)
    gfp = load_grayscale(record["channel1_path"])
    dna = load_grayscale(record["channel2_path"])
    return analyze_images(
        gfp,
        dna,
        metadata=record,
        config=config,
        illumination=load_reference_illumination(REFERENCE_ARCHIVE_PATH),
        compartment_config=REFERENCE_COMPARTMENT_CONFIG,
    )


def analyze_images(
    gfp: np.ndarray,
    dna: np.ndarray,
    *,
    metadata: Mapping[str, Any],
    config: SegmentationConfig = DEFAULT_CONFIG,
    illumination: IlluminationFunctions | None = None,
    compartment_config: CompartmentConfig | None = None,
) -> WellAnalysis:
    """Run the analysis pipeline over already-loaded channel arrays."""
    if gfp.shape != dna.shape:
        raise ValueError("GFP and DNA images must have identical dimensions.")
    if illumination is None:
        corrected_gfp = gfp.astype(np.float32)
        corrected_dna = dna.astype(np.float32)
    else:
        corrected_gfp = apply_illumination_correction(gfp, illumination.gfp)
        corrected_dna = apply_illumination_correction(dna, illumination.dna)

    original_labels = segment_nuclei(corrected_dna, config=config)
    if compartment_config is None:
        labels = original_labels
        cytoplasm_labels = None
    else:
        labels, cytoplasm_labels = build_distance_compartments(
            original_labels,
            compartment_config,
        )
    nuclei = quantify_nuclei(
        labels,
        corrected_gfp,
        cytoplasm_labels=cytoplasm_labels,
    )
    summary = summarize_nuclei(nuclei)
    return WellAnalysis(
        metadata=dict(metadata),
        gfp_image=gfp,
        dna_image=dna,
        corrected_gfp_image=corrected_gfp,
        corrected_dna_image=corrected_dna,
        labels=labels,
        cytoplasm_labels=cytoplasm_labels,
        nuclei=nuclei,
        summary=summary,
    )
