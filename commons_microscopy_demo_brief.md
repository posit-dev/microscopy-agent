# Commons microscopy demo: BBBC013 cytoplasm-to-nucleus translocation

## Purpose

This document is both:

1. a concept brief to review with a microscopy/image-analysis expert, and
2. an implementation brief for a coding agent to turn into a small Commons demo.

The demo is intended for a conference talk about **Commons as more than a BI agent**. The point is not that an LLM can “look at microscopy images.” The point is that an organization may already have a trusted domain-specific scientific workflow encoded in R or Python, and Commons can let a user invoke that workflow naturally and receive domain-specific outputs—including images—not just SQL results and generic charts.

This should be built as a polished illustrative demo, not represented as a validated scientific assay.

---

## The scenario

Imagine a translational biology group at a biotech company.

The lab runs fluorescence microscopy assays and has an image-analysis workflow maintained by a computational biologist or imaging/data scientist. That workflow is already the organization’s accepted way to segment nuclei, measure fluorescence, summarize wells, compare experimental conditions, and produce diagnostic visualizations.

A bench scientist is the user of the Commons agent. They know the experiment and biology but do not necessarily write Python or R. Instead of locating a notebook, editing parameters, and running the analysis manually, they ask questions such as:

> What happens to FKHR localization as we increase the Wortmannin dose?

> Show me an untreated well and a strongly responding treated well with the nuclei annotated.

> Is the response dose-dependent?

> Compare the Wortmannin and LY294002 dose responses.

Commons should route these questions to pre-authored image-analysis functions. The LLM chooses **which trusted workflow to invoke and with what arguments**; it does not invent the segmentation or quantification method.

That distinction is the reason this is a useful Commons example.

---

## Dataset: BBBC013

Use **BBBC013 v1** from the Broad Bioimage Benchmark Collection.

Dataset page:

https://bbbc.broadinstitute.org/BBBC013

Direct BMP archive (~31 MB):

https://data.broadinstitute.org/bbbc/BBBC013/BBBC013_v1_images_bmp.zip

Plate-map metadata:

https://data.broadinstitute.org/bbbc/BBBC013/BBBC013_v1_platemap_all.txt

https://data.broadinstitute.org/bbbc/BBBC013/BBBC013_v1_platemap_wortmannin.txt

https://data.broadinstitute.org/bbbc/BBBC013/BBBC013_v1_platemap_ly294002.txt

Reference materials used for illumination correction and compartment geometry:

https://data.broadinstitute.org/bbbc/BBBC013/BBBC013_reproduce_logan.zip

Optional visual plate map:

https://data.broadinstitute.org/bbbc/BBBC013/visual_plate_map.png

### What the experiment is

BBBC013 contains a 96-well fluorescence microscopy experiment using human U2OS osteosarcoma cells expressing FKHR-EGFP.

The experiment measures **cytoplasm-to-nucleus translocation of FKHR**. Treatment with Wortmannin or LY294002 inhibits PI3K/PKB signaling and leads to increased nuclear accumulation of FKHR-EGFP.

There are two images per well:

- **Channel 1:** FKHR-GFP
- **Channel 2:** DNA/nuclear stain (DRAQ)

Each image is 640 × 640 pixels, stored as an 8-bit BMP. There are 96 wells / 192 images.

The dataset includes four replicate dose curves for each of the two compounds, plus controls. BBBC describes it as a benchmarking dataset and provides published assay-quality results and a CellProfiler reference workflow.

The images are licensed **Creative Commons Attribution 3.0 Unported** by Ilya Ravkin. Preserve attribution in the project README and in any public demo materials where appropriate.

### File layout

The filenames encode channel and well location. Examples from an existing Python tutorial using this dataset include:

```text
Channel1-62-F-02.BMP
Channel2-62-F-02.BMP
```

The last two fields identify plate row and column; corresponding Channel1 and Channel2 files should be paired.

Do not rely on arbitrary directory ordering to pair files.

### Plate layout

The supplied metadata can be reshaped as an 8 × 12 plate.

Rows A–D correspond to the Wortmannin portion of the assay and rows E–H to the LY294002 portion. The existing tutorial listed in the references below reconstructs the controls and dose wells as follows:

- A–D: negative control in column 1, empty in column 2, Wortmannin dose series in columns 3–11, positive control in column 12.
- E–H: positive control in column 1, empty in column 2, LY294002 dose series in columns 3–11, negative control in column 12.

For the implementation, derive doses from the supplied plate-map files rather than transcribing them into code. Before making scientific claims about exactly what constitutes each positive control, compare the metadata, Broad documentation, and the reference CellProfiler pipeline.

---

## The scientific workflow we want to expose

The minimal workflow should be intentionally conventional and interpretable.

### 1. Load and pair the two channels

For a requested well, load its FKHR-GFP image and DNA image.

### 2. Segment nuclei from the DNA channel

Start with a simple classical image-processing pipeline, likely using `scikit-image`:

- optional light smoothing
- automatic thresholding, initially Otsu
- connected-component labeling
- removal of clearly tiny objects/debris
- optionally clearing border-touching objects
- only add watershed or more elaborate separation if the simple approach is visibly inadequate

Do **not** introduce Cellpose, SAM, deep learning, or a GPU dependency unless the simple method is clearly insufficient. For this demo, simplicity and transparency are features.

All thresholds/cleanup rules must live in the trusted workflow, not be invented by the LLM at runtime.

### 3. Measure FKHR signal in each nucleus

Using the nuclear segmentation mask, calculate at least:

- nucleus area
- mean FKHR-GFP intensity within each nucleus
- nucleus count per well

At the well level, calculate an appropriate summary of nuclear FKHR signal.

A simple public tutorial on BBBC013 uses mean nuclear GFP intensity as its demonstration measurement. That is a good initial implementation because it is easy to explain and reproduce.

The implemented reference-derived translocation proxy follows the distance
compartment in the published CellProfiler pipeline: expand each original
nucleus six pixels, assign overlaps to the nearest nucleus, remove the original
nucleus, and shrink the resulting cytoplasm and measurement nucleus by one
pixel. Measure mean illumination-corrected GFP in both compartments and report
the median per-cell cytoplasm:nucleus ratio for each well. Lower ratios indicate
greater relative nuclear accumulation.

### 4. Produce an annotated microscopy image

The primary domain-specific output should be a static image, preferably a Matplotlib figure or PNG.

A useful initial design:

- background: merged/composited GFP and DNA channels
- draw the segmented nuclear outlines
- optionally encode measured nuclear FKHR intensity visually
- include well ID and experimental condition in the title/caption
- avoid tiny text labels on every nucleus unless they actually improve readability

The most important visual fact is that the user can see the **raw biological image and the objects the trusted algorithm identified**.

### 5. Produce a dose-response view

For each compound, summarize nuclear FKHR signal for every dose and replicate and make a static dose-response plot.

For the first version:

- use a log dose axis
- show replicate wells, not only an aggregate
- show a mean/median summary across replicates
- show controls clearly
- do not fit a sophisticated pharmacological model unless there is a good reason

A fitted EC50/4-parameter logistic curve could be a nice later enhancement, but it should not be added just for visual polish unless the microscopy expert agrees it is appropriate for this assay and implementation.

---

## Questions for microscopy expert

Please pressure-test the following before we present this as a realistic scenario.

### Biological/measurement questions

1. Is “mean nuclear FKHR-GFP intensity” a defensible illustrative translocation metric for this dataset, or would you strongly prefer a nucleus/cytoplasm ratio or another measurement?
2. If a cytoplasmic measurement is preferable, what is the simplest defensible way to define cytoplasm here? Perinuclear ring? Approximate cell segmentation? Something else?
3. Should the result be described as “FKHR nuclear accumulation,” “FKHR translocation,” or something more precise?
4. Are there normalization or background-correction steps that would be conspicuously missing to a microscopy audience?
5. What is the most meaningful well-level statistic: mean, median, distributional summary, fraction of cells above a threshold, etc.?

### Segmentation questions

6. Is Otsu thresholding + connected components + size filtering a reasonable lightweight demonstration for the DRAQ channel?
7. Are touching nuclei common enough that watershed or another splitting step is necessary?
8. Should border-touching nuclei be discarded?
9. Is there a reasonable fixed minimum-area rule for these images, or should object-size filtering be derived from the image/data?

### Visualization questions

10. What would a microscopy expert most naturally want overlaid on the raw image: nuclear outlines, masks, per-cell intensity, classification, or something else?
11. Would side-by-side untreated vs. treated annotated images be visually compelling and scientifically honest?
12. What mistakes in an annotated image would immediately make this demo look naive to an imaging scientist?

### Story questions

13. Does the fictional workflow—bench scientist using an organization-approved image-analysis pipeline through a conversational interface—feel realistic?
14. Is there a better scientific question in BBBC013 than the proposed “does treatment increase nuclear FKHR?” / dose-response story?
15. Are there claims or words in this document that should be softened because this is a demonstration pipeline rather than a validated assay workflow?

---

## Recommended Commons capabilities

The exact API should follow the current Commons package and its bundled coding-agent skill. Commons is experimental and changing, so **do not invent or freeze an API based on this brief**. Inspect the installed/current checkout first.

Conceptually, expose a small semantic layer containing trusted measures along these lines.

### `annotate_well(well)`

Input:

```text
well: e.g. "A01", "D11", "H12"
```

Output:

- static annotated microscopy image
- numerical summary for the well:
  - number of segmented nuclei
  - well-level FKHR translocation/nuclear-signal statistic
  - treatment / dose / control metadata

This should be the star of the demo.

### `compare_wells(wells)` or `compare_conditions(...)`

Return a static side-by-side image panel for two or a small number of wells, with the same segmentation/annotation method applied to each.

Representative-well selection must be deterministic if a condition rather than a specific well is requested—for example, choose the replicate closest to the median response. Do not let the LLM cherry-pick a visually dramatic field.

### `dose_response(compound)`

Input:

```text
compound: "Wortmannin" or "LY294002"
```

Output:

- static dose-response plot
- compact numerical summary

All image processing and aggregation must occur in trusted code.

### `summarize_condition(compound, dose)` (optional)

Return a trusted numerical summary across the replicate wells matching a condition.

### `assay_quality(...)` (optional/later)

BBBC013 was designed partly around assay-quality benchmarking. A Z'-factor or similar measure could be an interesting additional domain-specific calculation, but it is not necessary for the core story and should only be added if implemented correctly.

---

## How Commons should be used

The demo should make the architecture visible in the code:

```text
natural-language question
        ↓
Commons searches trusted calculations
        ↓
trusted image-analysis measure
        ↓
segmentation / quantification / rendering
        ↓
static scientific image or plot + numerical result
        ↓
Verified answer provenance
```

The LLM should not:

- inspect pixel values itself and make a biological judgment
- generate arbitrary image-processing code on the trusted path
- choose thresholds at runtime
- silently change the segmentation method when something looks odd
- fabricate a “representative” sample
- replace a failed scientific workflow with a different ad hoc one

For the trusted path, the value proposition is precisely that those degrees of freedom have been removed.

Current Commons code explicitly supports the idea that a measure can build its own display result (for example, a plot or displayable table) and Commons then supplies the trusted provenance metadata around it. For this project, use the current supported static-image/plot mechanism. Prefer Matplotlib or Pillow/PNG. Do not reach for a Jupyter widget or arbitrary HTML unless necessary.

---

## Recommended implementation: Python

Python is probably the shortest path for this example because `scikit-image`, NumPy, Pandas, Matplotlib, Pillow, and SciPy provide everything required without specialized GUI infrastructure.

Suggested dependencies:

```text
commons
chatlas
pandas
numpy
scikit-image
matplotlib
Pillow
scipy       # only if needed
requests    # or stdlib urllib for data download
```

Pin versions or generate a lockfile once the demo works.

Use the current Commons instructions/agent skill to determine the exact model-provider dependencies and UI setup.

---

## Project structure

A reasonable starting structure:

```text
commons-microscopy/
├── README.md
├── pyproject.toml
├── uv.lock
├── app.py
├── agent.py
├── instructions.md
├── data/
│   ├── raw/                 # downloaded; gitignored
│   └── derived/             # generated metrics/cache; usually gitignored
├── measures/
│   ├── __init__.py
│   └── microscopy.py
├── microscopy/
│   ├── __init__.py
│   ├── dataset.py
│   ├── segmentation.py
│   ├── quantification.py
│   └── visualization.py
├── context/
│   └── assay.md
├── scripts/
│   ├── download_data.py
│   └── prepare_data.py
└── tests/
    ├── test_dataset.py
    ├── test_segmentation.py
    └── test_measures.py
```

Keep the scientific/image-processing code separate from the Commons measure wrappers. It should be possible to call and test the image-analysis functions directly without an LLM.

---

## Data download requirements

Implement `scripts/download_data.py`.

It should:

1. create `data/raw/`
2. download `BBBC013_v1_images_bmp.zip`
3. download the three plate-map text files
4. optionally download `visual_plate_map.png`
5. extract the image ZIP
6. verify that 192 BMP files are present: 96 Channel1 + 96 Channel2
7. verify that every well has exactly one Channel1/Channel2 pair
8. record or print a SHA-256 checksum of downloaded files for reproducibility
9. be idempotent: rerunning it should not redownload/reextract intact data unless explicitly requested

Optionally support a flag to download `BBBC013_reproduce_logan.zip` for scientific/reference inspection, but do not make that archive a runtime requirement.

Add downloaded files to `.gitignore`.

A simple invocation should be enough:

```bash
uv run python scripts/download_data.py
```

or the environment-equivalent command chosen for the project.

---

## Dataset parsing requirements

Build a canonical well metadata table with one row per well and fields similar to:

```text
well
row
column
channel1_path
channel2_path
condition_type
compound
dose
dose_unit
```

Parse filenames rather than depending on directory order.

Use the supplied plate-map files for doses. Construct control/compound labels carefully and test several known wells against the published plate layout.

Write unit tests for at least:

- pairing Channel1 and Channel2
- extracting A01/H12-style well IDs
- getting the correct compound for rows A–D vs. E–H
- identifying empty/control wells
- obtaining the expected dose for several representative wells

---

## Image-processing requirements

Keep the algorithm deterministic and documented.

Start with the simple workflow demonstrated in the external BBBC013 Python tutorial:

```text
DNA image
  → automatic threshold
  → binary nuclear mask
  → connected-component labels
  → remove implausibly small objects
  → region measurements using GFP image
```

Then improve it only where inspection of the data justifies the change.

The output for a well should include both:

1. **per-nucleus data**, e.g. label, area, nuclear GFP intensity, centroid
2. **well-level summary**, e.g. nucleus count and median/mean nuclear GFP intensity

Do not hardcode a scientific threshold for “translocated cell” unless the expert approves a definition. Continuous intensity visualization is safer for the first version.

---

## Performance and demo robustness

This is a live conference demo. Optimize for low latency and deterministic behavior.

The full 96-well plate can be processed once in `prepare_data.py`, producing a cached table such as:

```text
data/derived/well_metrics.parquet
```

Optionally cache per-nucleus measurements as well.

The annotation measure can process one requested well on demand because that is cheap and makes the workflow concrete.

The dose-response measure should preferably use values generated by the exact same trusted analysis pipeline, but it does not need to reprocess all 192 images during every chat turn.

Make the demo work without network access **after setup**. Data downloading belongs in setup, not in the live chat interaction.

---

## Context/instructions for the agent

Create a short context document explaining:

- what FKHR-EGFP is in this assay
- what the two channels represent
- what Wortmannin and LY294002 are doing in the context of this experiment
- what “nuclear FKHR signal” means in this implementation
- that this is an illustrative analysis, not a clinical or validated production assay
- limitations of the simplified segmentation/measurement method

The model may use that text to explain results, but numerical/image results on the trusted path must come from the measures.

The system/project instructions should strongly encourage the agent to use the registered measures for questions about nuclear localization, wells, treatment response, and dose response.

---

## Suggested live-demo conversation

### Prompt 1

> What happens to FKHR localization as we increase the Wortmannin dose?

Desired behavior: invoke the trusted dose-response workflow and display the scientific plot, then briefly interpret the direction of the response.

### Prompt 2

> Can you show me an untreated well next to a strongly responding treated well, with the nuclei annotated?

Desired behavior: invoke a trusted comparison/annotation workflow and return a static two-panel microscopy image.

If the measure selects representative wells itself, selection must be deterministic and documented.

### Prompt 3

> How does LY294002 compare?

Desired behavior: invoke the trusted dose-response workflow for LY294002 or an explicit cross-compound comparison.

This sequence moves from a natural-language biological question to an unmistakably non-BI visualization while keeping the scientific computation inside pre-authored code.

---

## Acceptance criteria

The project is ready for the conference demo when all of the following are true:

- One setup command downloads and validates BBBC013.
- One preparation command can generate any cached per-well metrics.
- The agent starts from a clean checkout with documented steps.
- Asking for a specific well produces a static annotated microscopy image inside the Commons conversation.
- The annotation visibly corresponds to nuclei in the DNA channel.
- Asking about Wortmannin dose response produces a static domain-appropriate plot.
- Asking about LY294002 works through the same trusted workflow.
- Trusted measure calls receive Commons' verified provenance treatment.
- The LLM is not generating image-analysis code on the trusted path.
- Scientific method choices and caveats are documented.
- Representative wells are selected deterministically, not aesthetically.
- Unit tests cover dataset parsing and core numerical behavior.
- There is a short README section attributing BBBC013 and linking to its license/source.
- The complete demo works offline after the initial setup/download step.

---

## Things deliberately out of scope for v1

Do not add these unless the basic demo is already excellent:

- user-uploaded microscopy images
- Cellpose/SAM/deep-learning segmentation
- GPU requirements
- interactive Jupyter widgets/anywidgets
- an elaborate custom Shiny UI
- cell phenotype classification
- LLM vision analysis
- image embeddings/vector search
- automatic scientific conclusions beyond what the trusted metrics support
- pharmacological curve fitting merely for aesthetics

The simplest version that produces a credible annotated image and a clear dose-response plot is the right first target.

---

## References

**Broad Bioimage Benchmark Collection, BBBC013**

https://bbbc.broadinstitute.org/BBBC013

The official dataset description documents the U2OS/FKHR experiment, two imaging channels, 96-well structure, 640 × 640 BMP images, dose curves, reference materials, and CC BY 3.0 license.

**Ljosa V, Sokolnicki KL, Carpenter AE (2012), “Annotated high-throughput microscopy image sets for validation,” Nature Methods 9(7):637.**

https://doi.org/10.1038/nmeth.2083

**Simple Python image-processing walkthrough using BBBC013**

https://guiwitz.github.io/ImagingStats/image_processing.html

This is useful implementation inspiration because it demonstrates downloading this exact archive, parsing the filenames, Otsu segmentation of the DNA channel, measuring GFP intensity per segmented nucleus with `scikit-image`, combining results with the plate metadata, and plotting treatment response. Treat it as an educational implementation, not as authoritative validation of the scientific method.

**Commons repository**

https://github.com/posit-dev/commons

**Commons introduction**

https://posit-dev.github.io/commons/articles/commons.html

Before implementation, the coding agent should inspect the current Commons package and bundled Commons coding-agent skill because the package is explicitly experimental and APIs may have changed.
