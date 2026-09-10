# Commons microscopy demo

This is a small Commons agent for the BBBC013 cytoplasm-to-nucleus
translocation image set. It demonstrates a conversational interface invoking a
pre-authored, deterministic microscopy workflow and returning annotated images
and dose-response plots with Commons provenance.

The implementation is deliberately illustrative. It segments nuclei from the
DRAQ channel with a fixed classical image-processing pipeline and reports
median nuclear FKHR-GFP intensity in 8-bit image units. That measurement is
useful for this demo, but it is not presented as a validated assay endpoint or
clinical analysis.

## Setup

The project currently uses the sibling Python Commons checkout at
`../commons/pkg-py`, matching Commons commit
`64b2c2ed482e0ab2d6df2dfeac88cea1527c1500`.

```bash
uv sync
uv run python scripts/download_data.py
uv run python scripts/prepare_data.py
```

Set a chatlas provider/model before starting the app. For example:

```bash
export CHATLAS_CHAT_PROVIDER_MODEL="openai/<model>"
uv run shiny run --reload app.py
```

`chatlas` loads the SDK and credentials required by the provider named in
`CHATLAS_CHAT_PROVIDER_MODEL`. The image data and cached analysis are local, so
the scientific workflow does not need network access after setup.

## Demo prompts

- What happens to FKHR localization as we increase the Wortmannin dose?
- Show me an untreated well next to a strongly responding treated well, with
  the nuclei annotated.
- How does LY294002 compare?
- Annotate well A01.

The model selects a registered measure and its arguments. Segmentation,
quantification, representative-well selection, aggregation, and rendering are
implemented in trusted code.

## Commands

```bash
# Download and validate the 192 BMP files and plate maps
uv run python scripts/download_data.py

# Re-download even if validated files already exist
uv run python scripts/download_data.py --force

# Also fetch the historical CellProfiler reference archive
uv run python scripts/download_data.py --with-reference

# Analyze all wells and cache per-well/per-nucleus Parquet files
uv run python scripts/prepare_data.py

# Run tests and lint
uv run pytest
uv run ruff check .
```

## Scientific method

For each well, the workflow:

1. pairs Channel 1 (FKHR-GFP) and Channel 2 (DRAQ/DNA) by parsed well ID;
2. lightly smooths the DNA image;
3. applies Otsu thresholding, fills small holes, removes debris, and clears
   border-touching objects;
4. labels the resulting nuclei;
5. measures area and mean FKHR-GFP intensity per nucleus; and
6. summarizes the well with the median and mean nuclear GFP intensity.

The public dose-response view uses the median nuclear GFP intensity, shows all
four replicate wells, and overlays the per-dose median. Negative and positive
controls appear in a separate control panel because zero dose cannot be placed
on a logarithmic axis. Representative wells are selected deterministically:
the well closest to the median response among the relevant control or highest
dose replicates.

The historical CellProfiler reference workflow includes illumination
correction, clump splitting, approximate cell/cytoplasm segmentation, and
nucleus-to-cytoplasm ratios. Those steps are intentionally outside this small
demo. This project should therefore say “nuclear FKHR signal” or “illustrative
nuclear accumulation,” not claim equivalence to the published assay workflow.

## Data and attribution

BBBC013 v1 was provided by Ilya Ravkin through the Broad Bioimage Benchmark
Collection. The images are licensed under the Creative Commons Attribution 3.0
Unported License.

Recommended citation from the collection:

> We used image set BBBC013v1 provided by Ilya Ravkin, available from the Broad
> Bioimage Benchmark Collection [Ljosa et al., Nature Methods, 2012].

Dataset page: <https://bbbc.broadinstitute.org/BBBC013>
