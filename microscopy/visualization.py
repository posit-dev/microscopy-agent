# ruff: noqa: E402

"""Static scientific figures for trusted measure results."""

from __future__ import annotations

import io
import os
from collections.abc import Sequence
from pathlib import Path

# Matplotlib and Fontconfig read these during import.
_CACHE_ROOT = Path(__file__).resolve().parents[1] / "data" / "derived" / ".cache"
os.environ.setdefault("MPLCONFIGDIR", str(_CACHE_ROOT / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(_CACHE_ROOT))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from skimage.segmentation import find_boundaries

from .analysis import WellAnalysis

GREEN = "#25a86b"
INK = "#172126"
MUTED = "#66747a"
YELLOW = "#f6c344"
GRID = "#dce3e5"


def _bounds(images: Sequence[np.ndarray]) -> tuple[float, float]:
    values = np.concatenate([image.ravel() for image in images])
    low, high = np.percentile(values, [1.0, 99.7])
    if high <= low:
        high = low + 1.0
    return float(low), float(high)


def _scale(image: np.ndarray, bounds: tuple[float, float]) -> np.ndarray:
    low, high = bounds
    return np.clip((image - low) / (high - low), 0, 1)


def _composite(
    analysis: WellAnalysis,
    gfp_bounds: tuple[float, float],
    dna_bounds: tuple[float, float],
) -> np.ndarray:
    return _display_image(
        analysis,
        channel="composite",
        overlay="nuclei",
        gfp_bounds=gfp_bounds,
        dna_bounds=dna_bounds,
    )


def _display_image(
    analysis: WellAnalysis,
    *,
    channel: str,
    overlay: str,
    gfp_bounds: tuple[float, float],
    dna_bounds: tuple[float, float],
) -> np.ndarray:
    gfp = _scale(analysis.gfp_image, gfp_bounds)
    dna = _scale(analysis.dna_image, dna_bounds)
    if channel == "composite":
        rgb = np.stack((dna * 0.78, gfp, dna), axis=-1)
    elif channel == "gfp":
        rgb = np.stack((np.zeros_like(gfp), gfp, np.zeros_like(gfp)), axis=-1)
    elif channel == "dna":
        rgb = np.stack((dna * 0.78, np.zeros_like(dna), dna), axis=-1)
    else:
        raise ValueError(f"Unsupported channel view: {channel}")
    if overlay == "nuclei":
        boundaries = find_boundaries(analysis.labels, mode="outer")
        rgb[boundaries] = np.array([1.0, 0.78, 0.12])
    elif overlay != "none":
        raise ValueError(f"Unsupported overlay view: {overlay}")
    return rgb


def _condition_line(metadata: dict[str, object]) -> str:
    return str(metadata["condition_label"])


def _style_image_axis(ax: Axes, analysis: WellAnalysis) -> None:
    ax.set_title(
        f"{analysis.metadata['well']}  ·  {_condition_line(analysis.metadata)}",
        loc="left",
        color=INK,
        fontsize=12,
        fontweight="bold",
        pad=10,
    )
    ax.text(
        0,
        -0.045,
        (
            f"{analysis.summary['nucleus_count']} nuclei  ·  "
            f"median nuclear GFP {analysis.summary['median_nuclear_gfp']:.1f}"
        ),
        transform=ax.transAxes,
        color=MUTED,
        fontsize=10,
        va="top",
    )
    ax.set_axis_off()


def _png_bytes(fig: plt.Figure) -> bytes:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buffer.getvalue()


def render_annotation(analysis: WellAnalysis) -> bytes:
    """Render one merged field with segmented nuclear outlines."""
    fig, ax = plt.subplots(figsize=(7.2, 7.7))
    ax.imshow(
        _composite(
            analysis,
            _bounds([analysis.gfp_image]),
            _bounds([analysis.dna_image]),
        )
    )
    _style_image_axis(ax, analysis)
    fig.suptitle(
        "FKHR-GFP (green) + DNA (magenta) · segmented nuclei (yellow)",
        x=0.125,
        y=0.985,
        ha="left",
        color=MUTED,
        fontsize=10,
    )
    fig.subplots_adjust(top=0.94, bottom=0.06)
    return _png_bytes(fig)


def render_parameterized_annotation(
    analysis: WellAnalysis,
    *,
    channel: str,
    overlay: str,
) -> bytes:
    """Render one uploaded sample with caller-selected display options."""
    fig, ax = plt.subplots(figsize=(7.2, 7.7))
    ax.imshow(
        _display_image(
            analysis,
            channel=channel,
            overlay=overlay,
            gfp_bounds=_bounds([analysis.gfp_image]),
            dna_bounds=_bounds([analysis.dna_image]),
        )
    )
    _style_image_axis(ax, analysis)
    fig.suptitle(
        f"Runtime upload analysis · channel={channel} · overlay={overlay}",
        x=0.125,
        y=0.985,
        ha="left",
        color=MUTED,
        fontsize=10,
    )
    fig.subplots_adjust(top=0.94, bottom=0.06)
    return _png_bytes(fig)


def render_comparison(analyses: Sequence[WellAnalysis]) -> bytes:
    """Render wells side by side using shared channel display scaling."""
    if len(analyses) < 2:
        raise ValueError("Comparison requires at least two wells.")
    gfp_bounds = _bounds([analysis.gfp_image for analysis in analyses])
    dna_bounds = _bounds([analysis.dna_image for analysis in analyses])
    fig, axes = plt.subplots(
        1,
        len(analyses),
        figsize=(6.2 * len(analyses), 6.9),
        squeeze=False,
    )
    for ax, analysis in zip(axes[0], analyses, strict=True):
        ax.imshow(_composite(analysis, gfp_bounds, dna_bounds))
        _style_image_axis(ax, analysis)
    fig.suptitle(
        "Shared display scaling · FKHR-GFP (green), DNA (magenta), nuclei (yellow)",
        x=0.08,
        y=0.995,
        ha="left",
        color=MUTED,
        fontsize=10,
    )
    fig.subplots_adjust(wspace=0.08, top=0.93, bottom=0.08)
    return _png_bytes(fig)


def render_parameterized_comparison(
    analyses: Sequence[WellAnalysis],
    *,
    channel: str,
    overlay: str,
) -> bytes:
    """Render uploaded samples with shared scaling and selected display options."""
    if len(analyses) < 2:
        raise ValueError("Comparison requires at least two uploaded samples.")
    gfp_bounds = _bounds([analysis.gfp_image for analysis in analyses])
    dna_bounds = _bounds([analysis.dna_image for analysis in analyses])
    fig, axes = plt.subplots(
        1,
        len(analyses),
        figsize=(6.2 * len(analyses), 6.9),
        squeeze=False,
    )
    for ax, analysis in zip(axes[0], analyses, strict=True):
        ax.imshow(
            _display_image(
                analysis,
                channel=channel,
                overlay=overlay,
                gfp_bounds=gfp_bounds,
                dna_bounds=dna_bounds,
            )
        )
        _style_image_axis(ax, analysis)
    fig.suptitle(
        f"Runtime upload comparison · shared {channel} scaling · overlay={overlay}",
        x=0.08,
        y=0.995,
        ha="left",
        color=MUTED,
        fontsize=10,
    )
    fig.subplots_adjust(wspace=0.08, top=0.93, bottom=0.08)
    return _png_bytes(fig)


def render_dose_response(metrics: pd.DataFrame, compound: str) -> bytes:
    """Render replicate dose wells and controls for one compound."""
    panel = metrics[metrics["series_compound"] == compound].copy()
    dose = panel[panel["condition_type"] == "dose"].copy()
    controls = panel[
        panel["condition_type"].isin(["negative_control", "positive_control"])
    ].copy()
    if dose.empty:
        raise ValueError(f"No dose-series metrics are available for {compound}.")

    unit = str(dose["dose_unit"].iloc[0])
    summary = (
        dose.groupby("dose", as_index=False)["median_nuclear_gfp"]
        .median()
        .sort_values("dose")
    )

    fig = plt.figure(figsize=(10.8, 5.8))
    grid = fig.add_gridspec(1, 2, width_ratios=[4.2, 1.25], wspace=0.12)
    ax = fig.add_subplot(grid[0, 0])
    control_ax = fig.add_subplot(grid[0, 1], sharey=ax)

    for replicate, group in dose.groupby("replicate"):
        group = group.sort_values("dose")
        ax.plot(
            group["dose"],
            group["median_nuclear_gfp"],
            color=GREEN,
            alpha=0.24,
            linewidth=1,
        )
        ax.scatter(
            group["dose"],
            group["median_nuclear_gfp"],
            color=GREEN,
            alpha=0.72,
            s=30,
            label=f"Replicate {replicate}",
        )

    ax.plot(
        summary["dose"],
        summary["median_nuclear_gfp"],
        color=INK,
        marker="o",
        markersize=5,
        linewidth=2.4,
        label="Median across replicates",
        zorder=4,
    )
    ax.set_xscale("log")
    ax.set_xlabel(f"{compound} dose ({unit})", color=INK)
    ax.set_ylabel("Median nuclear FKHR-GFP intensity (8-bit units)", color=INK)
    ax.grid(True, color=GRID, linewidth=0.8, alpha=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(colors=MUTED)
    ax.legend(frameon=False, fontsize=8, ncol=2, loc="upper left")

    order = ["negative_control", "positive_control"]
    labels = ["Negative", "150 nM\nWortmannin"]
    for x, (condition, label) in enumerate(zip(order, labels, strict=True)):
        values = controls.loc[
            controls["condition_type"] == condition, "median_nuclear_gfp"
        ]
        control_ax.scatter(
            np.full(len(values), x, dtype=float),
            values,
            color=YELLOW if condition == "positive_control" else MUTED,
            edgecolor=INK,
            linewidth=0.4,
            s=34,
            alpha=0.9,
        )
        if not values.empty:
            control_ax.hlines(
                values.median(),
                x - 0.25,
                x + 0.25,
                color=INK,
                linewidth=2,
            )
    control_ax.set_xticks([0, 1], labels)
    control_ax.set_title("Controls", color=INK, fontsize=10)
    control_ax.grid(True, axis="y", color=GRID, linewidth=0.8, alpha=0.8)
    control_ax.spines[["top", "right"]].set_visible(False)
    control_ax.tick_params(axis="y", labelleft=False)
    control_ax.tick_params(colors=MUTED)

    fig.suptitle(
        f"{compound} dose response",
        x=0.08,
        y=0.99,
        ha="left",
        color=INK,
        fontsize=17,
        fontweight="bold",
    )
    fig.text(
        0.08,
        0.935,
        "Each point is one well; the dark line is the median across four replicates.",
        color=MUTED,
        fontsize=10,
    )
    fig.subplots_adjust(top=0.84, bottom=0.16, left=0.1, right=0.97)
    return _png_bytes(fig)
