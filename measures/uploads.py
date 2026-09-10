"""Trusted measures for persistent user-uploaded microscopy images."""

from __future__ import annotations

import base64
from typing import Annotated, Any, Literal

import commons
import numpy as np
import sqlalchemy
from commons._provenance import TAG_EXTRA_KEY
from pydantic import Field

from microscopy.analysis import WellAnalysis, analyze_images, load_grayscale
from microscopy.segmentation import SegmentationConfig
from microscopy.uploads import fetch_upload
from microscopy.visualization import (
    render_parameterized_annotation,
    render_parameterized_comparison,
)

from .results import ScientificImageResult, scientific_image_result

ChannelView = Literal["composite", "gfp", "dna"]
OverlayView = Literal["nuclei", "none"]
CropView = Literal[
    "full",
    "center",
    "upper-left",
    "upper-right",
    "lower-left",
    "lower-right",
]


def _encode(
    png: bytes,
    *,
    model_text: str,
    alt_text: str,
    caption: str,
) -> ScientificImageResult:
    return scientific_image_result(
        value=model_text,
        image_base64=base64.b64encode(png).decode("ascii"),
        alt_text=alt_text,
        caption=caption,
        extra={TAG_EXTRA_KEY: commons.Tag.A},
    )


def _crop(
    gfp: np.ndarray,
    dna: np.ndarray,
    crop: CropView,
) -> tuple[np.ndarray, np.ndarray]:
    height, width = gfp.shape
    if crop == "full":
        bounds = (0, height, 0, width)
    elif crop == "center":
        bounds = (height // 4, height - height // 4, width // 4, width - width // 4)
    elif crop == "upper-left":
        bounds = (0, height // 2, 0, width // 2)
    elif crop == "upper-right":
        bounds = (0, height // 2, width // 2, width)
    elif crop == "lower-left":
        bounds = (height // 2, height, 0, width // 2)
    else:
        bounds = (height // 2, height, width // 2, width)
    top, bottom, left, right = bounds
    return gfp[top:bottom, left:right], dna[top:bottom, left:right]


def _config(
    gaussian_sigma: float,
    minimum_area: int,
    maximum_area: int,
    clear_border_objects: bool,
) -> SegmentationConfig:
    if maximum_area <= minimum_area:
        raise ValueError("maximum_area must be greater than minimum_area.")
    return SegmentationConfig(
        gaussian_sigma=gaussian_sigma,
        minimum_area=minimum_area,
        maximum_area=maximum_area,
        clear_border_objects=clear_border_objects,
    )


def _analyze_upload(
    uploads: sqlalchemy.Engine,
    upload_id: str,
    *,
    crop: CropView,
    config: SegmentationConfig,
) -> WellAnalysis:
    record = fetch_upload(uploads, upload_id)
    gfp, dna = _crop(
        load_grayscale(record["gfp_path"]),
        load_grayscale(record["dna_path"]),
        crop,
    )
    metadata = {
        **record,
        "well": upload_id,
        "condition_label": f"{record['sample_name']} · {crop} view",
    }
    return analyze_images(gfp, dna, metadata=metadata, config=config)


@commons.measure(
    description=(
        "List the persistent user-uploaded GFP and DNA image pairs that are "
        "currently available for analysis. Call this before analyzing uploads "
        "when the user did not give an exact upload ID."
    ),
    title="List uploaded microscopy samples",
)
def list_uploaded_samples(uploads: commons.Injected[Any]) -> list[dict[str, object]]:
    with uploads.connect() as connection:
        rows = connection.execute(
            sqlalchemy.text(
                """
                SELECT upload_id, sample_name, gfp_filename, dna_filename,
                       width, height, gfp_sha256, dna_sha256, created_at
                FROM uploads
                ORDER BY created_at DESC, upload_id
                """
            )
        ).mappings()
        return [dict(row) for row in rows]


@commons.measure(
    description=(
        "Analyze one persistent uploaded GFP/DNA image pair. The caller can vary "
        "the crop, displayed channel, segmentation overlay, Gaussian smoothing, "
        "nucleus area limits, and border handling. This is a deterministic "
        "parameter-sensitivity analysis over the uploaded pixels."
    ),
    title="Analyze an uploaded microscopy sample",
)
def analyze_uploaded_sample(
    upload_id: Annotated[
        str,
        Field(description="Exact persistent ID from list_uploaded_samples."),
    ],
    channel: Annotated[
        ChannelView,
        Field(description="Image channel or composite to display."),
    ] = "composite",
    overlay: Annotated[
        OverlayView,
        Field(description="Whether to draw segmented nuclear outlines."),
    ] = "nuclei",
    crop: Annotated[
        CropView,
        Field(description="Full image or a deterministic half/center crop."),
    ] = "full",
    gaussian_sigma: Annotated[
        float,
        Field(
            description="Gaussian smoothing sigma used before Otsu thresholding.",
            ge=0,
            le=5,
        ),
    ] = 1.0,
    minimum_area: Annotated[
        int,
        Field(description="Minimum retained nucleus area in pixels.", ge=5, le=5000),
    ] = 40,
    maximum_area: Annotated[
        int,
        Field(
            description="Maximum retained nucleus area in pixels.",
            ge=10,
            le=50000,
        ),
    ] = 1200,
    clear_border_objects: Annotated[
        bool,
        Field(description="Whether to remove objects touching the crop border."),
    ] = True,
    uploads: commons.Injected[Any] = None,
) -> ScientificImageResult:
    config = _config(
        gaussian_sigma,
        minimum_area,
        maximum_area,
        clear_border_objects,
    )
    analysis = _analyze_upload(uploads, upload_id, crop=crop, config=config)
    summary = analysis.summary
    parameters = (
        f"crop={crop}, channel={channel}, overlay={overlay}, "
        f"gaussian_sigma={gaussian_sigma:g}, minimum_area={minimum_area}, "
        f"maximum_area={maximum_area}, "
        f"clear_border_objects={clear_border_objects}"
    )
    return _encode(
        render_parameterized_annotation(
            analysis,
            channel=channel,
            overlay=overlay,
        ),
        model_text=(
            f"Analyzed persistent upload {upload_id} "
            f"({analysis.metadata['sample_name']}) with {parameters}. "
            f"Segmented nuclei: {summary['nucleus_count']}. Median nuclear GFP: "
            f"{summary['median_nuclear_gfp']:.2f}; mean nuclear GFP: "
            f"{summary['mean_nuclear_gfp']:.2f}. The generated image is visible "
            "to the user."
        ),
        alt_text=(
            f"Runtime analysis of uploaded microscopy sample {upload_id}, "
            f"displaying {channel} with {overlay} overlay."
        ),
        caption=(
            f"Generated from persistent upload {upload_id}. {parameters}. "
            f"{summary['nucleus_count']} nuclei segmented."
        ),
    )


@commons.measure(
    description=(
        "Compare two to four persistent uploaded GFP/DNA image pairs with the "
        "same crop, display, and segmentation parameters and shared channel "
        "scaling."
    ),
    title="Compare uploaded microscopy samples",
)
def compare_uploaded_samples(
    upload_ids: Annotated[
        list[str],
        Field(
            description="Two to four exact IDs from list_uploaded_samples.",
            min_length=2,
            max_length=4,
        ),
    ],
    channel: Annotated[
        ChannelView,
        Field(description="Image channel or composite to display."),
    ] = "composite",
    overlay: Annotated[
        OverlayView,
        Field(description="Whether to draw segmented nuclear outlines."),
    ] = "nuclei",
    crop: Annotated[
        CropView,
        Field(description="Crop applied independently to every uploaded sample."),
    ] = "full",
    gaussian_sigma: Annotated[
        float,
        Field(description="Gaussian smoothing sigma.", ge=0, le=5),
    ] = 1.0,
    minimum_area: Annotated[
        int,
        Field(description="Minimum retained nucleus area in pixels.", ge=5, le=5000),
    ] = 40,
    maximum_area: Annotated[
        int,
        Field(
            description="Maximum retained nucleus area in pixels.",
            ge=10,
            le=50000,
        ),
    ] = 1200,
    clear_border_objects: Annotated[
        bool,
        Field(description="Whether to remove objects touching crop borders."),
    ] = True,
    uploads: commons.Injected[Any] = None,
) -> ScientificImageResult:
    if len(set(upload_ids)) != len(upload_ids):
        raise ValueError("Each upload ID in a comparison must be distinct.")
    config = _config(
        gaussian_sigma,
        minimum_area,
        maximum_area,
        clear_border_objects,
    )
    analyses = [
        _analyze_upload(uploads, upload_id, crop=crop, config=config)
        for upload_id in upload_ids
    ]
    details = "; ".join(
        (
            f"{analysis.metadata['upload_id']}: "
            f"{analysis.summary['nucleus_count']} nuclei, median GFP "
            f"{analysis.summary['median_nuclear_gfp']:.2f}"
        )
        for analysis in analyses
    )
    return _encode(
        render_parameterized_comparison(
            analyses,
            channel=channel,
            overlay=overlay,
        ),
        model_text=(
            f"Compared persistent uploads with crop={crop}, channel={channel}, "
            f"overlay={overlay}, gaussian_sigma={gaussian_sigma:g}, "
            f"minimum_area={minimum_area}, maximum_area={maximum_area}, "
            f"clear_border_objects={clear_border_objects}. {details}. "
            "The generated comparison is visible to the user."
        ),
        alt_text="Runtime comparison of persistent uploaded microscopy samples.",
        caption=(
            f"Persistent uploads: {', '.join(upload_ids)}. crop={crop}; "
            f"channel={channel}; overlay={overlay}; sigma={gaussian_sigma:g}; "
            f"area={minimum_area}–{maximum_area}px."
        ),
    )
