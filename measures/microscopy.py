"""Trusted Commons measures for the BBBC013 demo."""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

import commons
import pandas as pd
from commons._provenance import TAG_EXTRA_KEY
from pydantic import Field

from microscopy.analysis import ANALYSIS_VERSION, WellAnalysis, analyze_well
from microscopy.dataset import build_well_metadata, normalize_well
from microscopy.visualization import (
    render_annotation,
    render_comparison,
    render_dose_response,
)

from .results import ScientificImageResult, scientific_image_result

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
DERIVED_DIR = PROJECT_ROOT / "data" / "derived"
WELL_METRICS_PATH = DERIVED_DIR / "well_metrics.parquet"
NUCLEUS_METRICS_PATH = DERIVED_DIR / "nucleus_metrics.parquet"
PROVENANCE = (
    "https://bbbc.broadinstitute.org/BBBC013 (retrieved 2026-09-10)",
    "commons_microscopy_demo_brief.md",
)
COMPOUND = Literal["Wortmannin", "LY294002"]


@lru_cache(maxsize=1)
def metadata_table() -> pd.DataFrame:
    return build_well_metadata(RAW_DIR)


def _metadata_row(well: str) -> pd.Series:
    normalized = normalize_well(well)
    rows = metadata_table().loc[lambda frame: frame["well"] == normalized]
    if rows.empty:
        raise ValueError(f"Well {normalized} is not present in BBBC013.")
    return rows.iloc[0]


def _analysis(well: str) -> WellAnalysis:
    return analyze_well(_metadata_row(well))


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


def _prepare_metrics() -> pd.DataFrame:
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    well_rows: list[dict[str, object]] = []
    nucleus_rows: list[pd.DataFrame] = []
    for _, metadata in metadata_table().iterrows():
        analysis = analyze_well(metadata)
        well_rows.append(
            {
                **metadata.to_dict(),
                **analysis.summary,
                "analysis_version": ANALYSIS_VERSION,
            }
        )
        nuclei = analysis.nuclei.copy()
        nuclei.insert(0, "well", metadata["well"])
        nucleus_rows.append(nuclei)

    well_metrics = pd.DataFrame(well_rows)
    nucleus_metrics = pd.concat(nucleus_rows, ignore_index=True)
    well_metrics.to_parquet(WELL_METRICS_PATH, index=False)
    nucleus_metrics.to_parquet(NUCLEUS_METRICS_PATH, index=False)
    return well_metrics


@lru_cache(maxsize=1)
def well_metrics() -> pd.DataFrame:
    if WELL_METRICS_PATH.exists():
        metrics = pd.read_parquet(WELL_METRICS_PATH)
        versions = set(metrics.get("analysis_version", []))
        if versions == {ANALYSIS_VERSION}:
            return metrics
    return _prepare_metrics()


def representative_well(
    candidates: pd.DataFrame,
    *,
    metric: str = "median_nuclear_gfp",
) -> str:
    """Select the replicate closest to the candidate median, breaking ties by well."""
    if candidates.empty:
        raise ValueError("No wells match the requested condition.")
    target = float(candidates[metric].median())
    ranked = candidates.assign(
        distance=(candidates[metric] - target).abs()
    ).sort_values(
        ["distance", "well"],
    )
    return str(ranked.iloc[0]["well"])


@commons.measure(
    description=(
        "Annotate one BBBC013 well with the trusted nuclear segmentation and "
        "return its condition, nucleus count, and nuclear FKHR-GFP summary."
    ),
    title="Annotate a microscopy well",
    provenance=PROVENANCE,
)
def annotate_well(
    well: Annotated[
        str,
        Field(description="BBBC013 well identifier from A01 through H12."),
    ],
) -> ScientificImageResult:
    analysis = _analysis(well)
    meta = analysis.metadata
    summary = analysis.summary
    text = (
        f"Annotated well {meta['well']} ({meta['condition_label']}). "
        f"Segmented nuclei: {summary['nucleus_count']}. "
        f"Median nuclear FKHR-GFP intensity: "
        f"{summary['median_nuclear_gfp']:.2f} 8-bit units; mean: "
        f"{summary['mean_nuclear_gfp']:.2f}. "
        "The annotated microscopy image is already visible to the user."
    )
    return _encode(
        render_annotation(analysis),
        model_text=text,
        alt_text=(
            f"Composite microscopy image for well {meta['well']} with segmented "
            "nuclear outlines."
        ),
        caption=(
            "Yellow outlines are nuclei segmented from the DNA channel. "
            "Green is FKHR-GFP; magenta is DNA."
        ),
    )


@commons.measure(
    description=(
        "Compare two to four explicitly named BBBC013 wells in one annotated "
        "microscopy panel using identical segmentation and shared display scaling."
    ),
    title="Compare microscopy wells",
    provenance=PROVENANCE,
)
def compare_wells(
    wells: Annotated[
        list[str],
        Field(
            description="Two to four BBBC013 well identifiers.",
            min_length=2,
            max_length=4,
        ),
    ],
) -> ScientificImageResult:
    normalized = [normalize_well(well) for well in wells]
    if len(set(normalized)) != len(normalized):
        raise ValueError("Each comparison well must be distinct.")
    analyses = [_analysis(well) for well in normalized]
    details = "; ".join(
        (
            f"{analysis.metadata['well']} ({analysis.metadata['condition_label']}): "
            f"{analysis.summary['nucleus_count']} nuclei, median nuclear GFP "
            f"{analysis.summary['median_nuclear_gfp']:.2f}"
        )
        for analysis in analyses
    )
    return _encode(
        render_comparison(analyses),
        model_text=(
            f"Compared wells with the same trusted workflow: {details}. "
            "The comparison image is already visible to the user."
        ),
        alt_text="Side-by-side annotated BBBC013 microscopy wells.",
        caption=(
            "Channel display limits are shared across panels. Yellow outlines "
            "show the nuclei used for quantification."
        ),
    )


@commons.measure(
    description=(
        "Compare a deterministic representative untreated well with a "
        "representative highest-dose treated well for one compound. Each well "
        "is the replicate closest to its condition's median response."
    ),
    title="Compare untreated and treated wells",
    provenance=PROVENANCE,
)
def compare_conditions(
    compound: Annotated[
        COMPOUND,
        Field(description="Dose-series compound to compare."),
    ] = "Wortmannin",
) -> ScientificImageResult:
    metrics = well_metrics()
    panel = metrics[metrics["series_compound"] == compound]
    untreated = panel[panel["condition_type"] == "negative_control"]
    highest_dose = float(
        panel.loc[panel["condition_type"] == "dose", "dose"].max()
    )
    treated = panel[
        (panel["condition_type"] == "dose") & (panel["dose"] == highest_dose)
    ]
    wells = [
        representative_well(untreated),
        representative_well(treated),
    ]
    analyses = [_analysis(well) for well in wells]
    return _encode(
        render_comparison(analyses),
        model_text=(
            f"Deterministically selected {wells[0]} as the untreated {compound} "
            f"representative and {wells[1]} as the highest-dose ({highest_dose:g} "
            f"{treated.iloc[0]['dose_unit']}) representative. Selection used the "
            "replicate closest to each condition median. The annotated comparison "
            "is already visible to the user."
        ),
        alt_text=(
            f"Untreated and highest-dose {compound} BBBC013 wells with segmented "
            "nuclei."
        ),
        caption=(
            "Representative wells are selected by a fixed median-response rule, "
            "not by visual appearance."
        ),
    )


@commons.measure(
    description=(
        "Plot the trusted BBBC013 dose response for Wortmannin or LY294002. "
        "Shows all four replicate wells, the per-dose median, and negative and "
        "positive controls."
    ),
    title="Microscopy dose response",
    provenance=PROVENANCE,
)
def dose_response(
    compound: Annotated[
        COMPOUND,
        Field(description="Compound whose dose response should be shown."),
    ],
) -> ScientificImageResult:
    metrics = well_metrics()
    panel = metrics[
        (metrics["series_compound"] == compound)
        & (metrics["condition_type"] == "dose")
    ].copy()
    summary = (
        panel.groupby(["dose", "dose_unit"], as_index=False)["median_nuclear_gfp"]
        .median()
        .sort_values("dose")
    )
    first = summary.iloc[0]
    last = summary.iloc[-1]
    peak = summary.loc[summary["median_nuclear_gfp"].idxmax()]
    ratio = float(last["median_nuclear_gfp"] / first["median_nuclear_gfp"])
    per_dose = ", ".join(
        (
            f"{row.dose:g} {row.dose_unit}: "
            f"{row.median_nuclear_gfp:.2f}"
        )
        for row in summary.itertuples(index=False)
    )
    text = (
        f"{compound} per-dose median nuclear GFP values are {per_dose}. "
        f"The observed maximum is {peak['median_nuclear_gfp']:.2f} at "
        f"{peak['dose']:g} {peak['dose_unit']}. The lowest dose "
        f"({first['dose']:g} {first['dose_unit']}) is "
        f"{first['median_nuclear_gfp']:.2f}; the highest dose "
        f"({last['dose']:g} {last['dose_unit']}) is "
        f"{last['median_nuclear_gfp']:.2f}. "
        f"Highest/lowest ratio: {ratio:.2f}. "
        "The replicate-level dose-response plot is already visible to the user."
    )
    return _encode(
        render_dose_response(metrics, compound),
        model_text=text,
        alt_text=(
            f"Dose-response plot for {compound} showing four replicate wells, "
            "their median, and controls."
        ),
        caption=(
            "The response metric is median nuclear FKHR-GFP intensity from the "
            "fixed demonstration workflow. Positive controls are 150 nM "
            "Wortmannin."
        ),
    )


@commons.measure(
    description=(
        "Return the trusted numerical summary across replicate dose wells for "
        "one exact compound and dose."
    ),
    title="Summarize a microscopy condition",
    provenance=PROVENANCE,
)
def summarize_condition(
    compound: Annotated[
        COMPOUND,
        Field(description="Dose-series compound."),
    ],
    dose: Annotated[
        float,
        Field(description="Exact numeric dose from the BBBC013 plate map."),
    ],
) -> dict[str, object]:
    rows = well_metrics()[
        (well_metrics()["series_compound"] == compound)
        & (well_metrics()["condition_type"] == "dose")
        & (well_metrics()["dose"] == dose)
    ]
    if rows.empty:
        available = sorted(
            well_metrics()
            .loc[
                (well_metrics()["series_compound"] == compound)
                & (well_metrics()["condition_type"] == "dose"),
                "dose",
            ]
            .unique()
        )
        raise ValueError(f"No {compound} dose {dose:g}; available doses: {available}.")
    return {
        "compound": compound,
        "dose": float(dose),
        "dose_unit": str(rows.iloc[0]["dose_unit"]),
        "replicate_wells": rows["well"].tolist(),
        "replicate_count": int(len(rows)),
        "median_of_well_medians": float(rows["median_nuclear_gfp"].median()),
        "minimum_well_median": float(rows["median_nuclear_gfp"].min()),
        "maximum_well_median": float(rows["median_nuclear_gfp"].max()),
        "median_nucleus_count": float(rows["nucleus_count"].median()),
    }
