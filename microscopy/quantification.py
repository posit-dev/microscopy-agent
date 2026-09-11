"""Per-nucleus and per-well FKHR-GFP measurements."""

from __future__ import annotations

import numpy as np
import pandas as pd
from skimage import measure


def quantify_nuclei(
    labels: np.ndarray,
    gfp_image: np.ndarray,
    *,
    cytoplasm_labels: np.ndarray | None = None,
) -> pd.DataFrame:
    """Measure nuclear GFP and an optional matched cytoplasmic compartment."""
    if labels.shape != gfp_image.shape:
        raise ValueError("Label and GFP images must have identical dimensions.")
    if cytoplasm_labels is not None and cytoplasm_labels.shape != labels.shape:
        raise ValueError(
            "Nuclear labels, cytoplasmic labels, and GFP image must match."
        )
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
        columns = [
            "label",
            "area",
            "centroid_y",
            "centroid_x",
            "mean_nuclear_gfp",
            "integrated_nuclear_gfp",
        ]
        if cytoplasm_labels is not None:
            columns.extend(
                [
                    "cytoplasm_area",
                    "mean_cytoplasmic_gfp",
                    "integrated_cytoplasmic_gfp",
                    "cytoplasm_to_nucleus_ratio",
                ]
            )
        return pd.DataFrame(columns=columns)
    nuclei["integrated_nuclear_gfp"] = (
        nuclei["area"] * nuclei["mean_nuclear_gfp"]
    )
    if cytoplasm_labels is not None:
        cytoplasm = pd.DataFrame(
            measure.regionprops_table(
                cytoplasm_labels,
                intensity_image=gfp_image.astype(np.float32),
                properties=("label", "area", "mean_intensity"),
            )
        ).rename(
            columns={
                "area": "cytoplasm_area",
                "mean_intensity": "mean_cytoplasmic_gfp",
            }
        )
        nuclei = nuclei.merge(
            cytoplasm,
            on="label",
            how="left",
            validate="one_to_one",
        )
        nuclei["integrated_cytoplasmic_gfp"] = (
            nuclei["cytoplasm_area"] * nuclei["mean_cytoplasmic_gfp"]
        )
        nuclei["cytoplasm_to_nucleus_ratio"] = np.divide(
            nuclei["mean_cytoplasmic_gfp"],
            nuclei["mean_nuclear_gfp"],
            out=np.full(len(nuclei), np.nan, dtype=float),
            where=nuclei["mean_nuclear_gfp"].to_numpy() > 0,
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
    summary: dict[str, float | int] = {
        "nucleus_count": int(len(nuclei)),
        "mean_nuclear_gfp": float(nuclei["mean_nuclear_gfp"].mean()),
        "median_nuclear_gfp": float(nuclei["mean_nuclear_gfp"].median()),
    }
    if "cytoplasm_to_nucleus_ratio" in nuclei:
        valid_ratios = nuclei["cytoplasm_to_nucleus_ratio"].replace(
            [np.inf, -np.inf],
            np.nan,
        ).dropna()
        summary.update(
            {
                "ratio_nucleus_count": int(len(valid_ratios)),
                "mean_cytoplasm_to_nucleus_ratio": float(valid_ratios.mean()),
                "median_cytoplasm_to_nucleus_ratio": float(valid_ratios.median()),
            }
        )
    return summary
