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
from .segmentation import DEFAULT_CONFIG, SegmentationConfig, segment_nuclei

ANALYSIS_VERSION = "nuclear-gfp-v1"


@dataclass
class WellAnalysis:
    """All trusted outputs for one well."""

    metadata: dict[str, Any]
    gfp_image: np.ndarray
    dna_image: np.ndarray
    labels: np.ndarray
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
    labels = segment_nuclei(dna, config=config)
    nuclei = quantify_nuclei(labels, gfp)
    summary = summarize_nuclei(nuclei)
    return WellAnalysis(
        metadata=record,
        gfp_image=gfp,
        dna_image=dna,
        labels=labels,
        nuclei=nuclei,
        summary=summary,
    )
