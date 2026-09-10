"""Per-nucleus and per-well FKHR-GFP measurements."""

from __future__ import annotations

import numpy as np
import pandas as pd
from skimage import measure


def quantify_nuclei(labels: np.ndarray, gfp_image: np.ndarray) -> pd.DataFrame:
    """Measure area, centroid, and nuclear GFP intensity for each nucleus."""
    if labels.shape != gfp_image.shape:
        raise ValueError("Label and GFP images must have identical dimensions.")
    table = measure.regionprops_table(
        labels,
        intensity_image=gfp_image.astype(np.float32),
        properties=("label", "area", "centroid", "mean_intensity"),
    )
    nuclei = pd.DataFrame(table).rename(
        columns={
            "centroid-0": "centroid_y",
            "centroid-1": "centroid_x",
            "mean_intensity": "mean_nuclear_gfp",
        }
    )
    if nuclei.empty:
        return pd.DataFrame(
            columns=[
                "label",
                "area",
                "centroid_y",
                "centroid_x",
                "mean_nuclear_gfp",
                "integrated_nuclear_gfp",
            ]
        )
    nuclei["integrated_nuclear_gfp"] = (
        nuclei["area"] * nuclei["mean_nuclear_gfp"]
    )
    return nuclei


def summarize_nuclei(nuclei: pd.DataFrame) -> dict[str, float | int]:
    """Create the trusted well-level nuclear-signal summary."""
    if nuclei.empty:
        return {
            "nucleus_count": 0,
            "mean_nuclear_gfp": float("nan"),
            "median_nuclear_gfp": float("nan"),
        }
    return {
        "nucleus_count": int(len(nuclei)),
        "mean_nuclear_gfp": float(nuclei["mean_nuclear_gfp"].mean()),
        "median_nuclear_gfp": float(nuclei["mean_nuclear_gfp"].median()),
    }
