# Commons microscopy demo

This is a small Commons agent for the BBBC013 cytoplasm-to-nucleus
translocation image set. It demonstrates a conversational interface invoking a
pre-authored, deterministic microscopy workflow and returning annotated images
and dose-response plots with Commons provenance. It also accepts persistent
user-uploaded GFP/DNA image pairs and analyzes them with runtime-selected
parameters.

The implementation is deliberately illustrative. It segments nuclei from the
DRAQ channel with a fixed classical image-processing pipeline and reports
median nuclear FKHR-GFP intensity in illumination-corrected 8-bit image units.
It also exposes a reference-derived cytoplasm-to-nucleus ratio using the
distance-compartment geometry from the published CellProfiler pipelines. These
measurements are useful for this demo, but they are not presented as validated
assay endpoints or clinical analysis.

## Setup

The project installs Python Commons from
`https://github.com/posit-dev/commons.git`, pinned to commit
`8614f48b5aff2ad20500cf29fcd2e295777b847c`.

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

- What happens to nuclear FKHR signal as we increase the Wortmannin dose?
- Show the reference-derived cytoplasm-to-nucleus response for Wortmannin.
- Show me an untreated well next to a strongly responding treated well, with
  the nuclei annotated.
- How does LY294002 compare?
- Annotate well A01.
- Analyze my uploaded sample with the DNA channel shown and no overlay.
- Re-run my upload using the center crop and a minimum nucleus area of 100.
- Compare my two uploaded samples with shared GFP scaling.

The model selects a registered measure and its arguments. Segmentation,
quantification, representative-well selection, aggregation, and rendering are
implemented in trusted code.

## Persistent uploads

The `page_chat` sidebar uses ordinary Shiny file inputs to register a matching
GFP and DNA image pair. PNG, JPEG, BMP, and TIFF files are accepted. The
channels must have identical dimensions.

Uploaded files and their SQLite inventory are stored permanently under
`data/uploads/`, which is excluded from Git. Each pair receives an ID such as
`patient-7-baseline-a1b2c3d4e5`. The sidebar shows that ID, and a trusted
measure lets the agent read the current inventory without exposing private
server paths.

The upload controls share the sidebar with shinychat's native conversation
history, including New Chat, search, restore, rename, and delete controls.
The session-local agent is connected through `commons.ui.server()`, so Commons
uses shinychat's native Chatlas history path and queues its restore reminder
when a stored conversation is reopened.

Upload measures take the public ID and optional crop, display, and segmentation
parameters. Commons injects the private upload database into those measures;
the model does not receive server file paths. When a user does not supply an
exact ID, the agent calls the trusted upload-list measure against the current
database. Changing the crop or segmentation parameters recomputes the analysis
from the stored pixels.

## Commands

```bash
# Download and validate the images, plate maps, and reference illumination maps
uv run python scripts/download_data.py

# Re-download even if validated files already exist
uv run python scripts/download_data.py --force

# Backward-compatible alias; the reference archive is now downloaded by default
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
2. divides each channel by the published BBBC013 illumination function;
3. lightly smooths the corrected DNA image;
4. applies Otsu thresholding, fills small holes, removes debris, and clears
   border-touching objects;
5. labels the resulting nuclei;
6. constructs the reference distance compartment by expanding each original
   nucleus six pixels, assigning overlaps to the nearest nucleus, subtracting
   the original nucleus, and shrinking the cytoplasm and measurement nucleus by
   one pixel;
7. measures corrected mean FKHR-GFP intensity in each matched nucleus and
   cytoplasmic compartment; and
8. summarizes the well with nuclear GFP intensity and the cytoplasm:nucleus
   mean-intensity ratio.

The public dose-response view uses the median nuclear GFP intensity, shows all
four replicate wells, and overlays the per-dose median. Negative and positive
controls appear in a separate control panel because zero dose cannot be placed
on a logarithmic axis. Representative wells are selected deterministically:
the well closest to the median response among the relevant control or highest
dose replicates.

The distance cytoplasm and illumination functions come directly from
`BBBC013_reproduce_logan.zip`. The historical CellProfiler workflow also uses
MoG nuclear thresholding, intensity-based clump splitting, GFP propagation, a
large feature library, and experiment-specific classification thresholds.
Those remaining steps are outside this demo. The continuous cytoplasm:nucleus
ratio is therefore a reference-derived translocation proxy, not an exact
reproduction of the paper's top classified feature. Nuclear intensity remains
the simple public measurement.

## Data and attribution

BBBC013 v1 was provided by Ilya Ravkin through the Broad Bioimage Benchmark
Collection. The images are licensed under the Creative Commons Attribution 3.0
Unported License.

Recommended citation from the collection:

> We used image set BBBC013v1 provided by Ilya Ravkin, available from the Broad
> Bioimage Benchmark Collection [Ljosa et al., Nature Methods, 2012].

Dataset page: <https://bbbc.broadinstitute.org/BBBC013>
