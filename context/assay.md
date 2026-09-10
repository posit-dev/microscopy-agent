---
provenance: https://bbbc.broadinstitute.org/BBBC013 (retrieved 2026-09-10)
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
mean Channel 1 intensity within nuclei segmented from Channel 2. Intensities
are reported in the original 8-bit image units. It is an interpretable
illustrative metric, not the full published CellProfiler endpoint.

The simplified workflow does not apply the reference illumination-correction
images, segment whole cells, measure cytoplasmic intensity, or calculate a
nucleus-to-cytoplasm ratio. It should not be represented as a validated
production assay, a clinical result, or an exact reproduction of published
BBBC013 assay-quality results.

The Broad documentation identifies the shared positive control as 150 nM
Wortmannin. In rows E-H it appears in column 1; LY294002 negative controls are
in column 12.
