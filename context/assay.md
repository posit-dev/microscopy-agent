---
provenance:
  - https://bbbc.broadinstitute.org/BBBC015
  - https://doi.org/10.1177/1087057110370895
  - BBBC013_reproduce_logan.zip (SHA-256 5ab59bbaddf75fee08436d2d7cfc7460ebfdaa6fdf1b8adb71274c7c27f885f3)
---

# BBBC013 assay context

BBBC013 contains one 96-well plate of human U2OS osteosarcoma cells expressing
FKHR-EGFP. Channel 1 is FKHR-GFP and Channel 2 is the DRAQ DNA stain used to
identify nuclei.

In proliferating cells, FKHR is predominantly cytoplasmic. In this experiment,
Wortmannin or LY294002 inhibits PI3K/PKB signaling, leading to increased nuclear
accumulation of FKHR-EGFP. Rows A-D contain the Wortmannin dose series and rows
E-H contain the LY294002 dose series, each with four replicate rows.

This implementation defines “nuclear FKHR signal” as the median of per-nucleus
mean Channel 1 intensity within nuclei segmented from Channel 2. Both channels
are divided by the illumination functions supplied in the Broad reproduction
archive, so nuclear intensity is reported in illumination-corrected 8-bit
units. It remains an interpretable illustrative metric.

The workflow also implements the published distance-based cytoplasmic
compartment. Each original nuclear label is expanded six pixels with overlap
assigned to the nearest nucleus. The original nucleus is removed, and the
resulting cytoplasmic compartment and measurement nucleus are each shrunk by
one pixel. The continuous per-cell metric is mean cytoplasmic FKHR-GFP divided
by mean nuclear FKHR-GFP; the well summary is its median. Lower values indicate
greater relative nuclear accumulation.

The reference CellProfiler pipelines additionally use MoG nuclear thresholding,
intensity-based clump splitting, GFP-based cell propagation, broad feature
screening, and tuned classification thresholds. The Python implementation does
not reproduce those steps. Describe its ratio as a reference-derived
translocation proxy, not the paper's validated top feature or an exact
reproduction of its Z' and V factors.

The Broad documentation identifies the shared positive control as 150 nM
Wortmannin. In rows E-H it appears in column 1; LY294002 negative controls are
in column 12.
