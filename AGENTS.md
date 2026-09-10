# Project guidance

This project is a conference demo of a Commons agent over BBBC013 microscopy
images. The trusted path is the code in `microscopy/` and `measures/`; model
instructions must never invite the model to invent segmentation parameters,
choose a visually dramatic replicate, or substitute ad hoc image analysis.

The public measurement is median nuclear FKHR-GFP intensity in 8-bit image
units. Treat it as an illustrative nuclear-signal metric, not a validated
translocation score. Keep the segmentation and aggregation deterministic and
document any scientific-method changes in the README and assay context.

Dose-series values come from the supplied Broad plate maps. Rows E-H, column 1
are the shared positive control (150 nM Wortmannin), as documented by Broad and
the corrected reference CellProfiler metadata; they are not 80 µM LY294002.

Downloaded BBBC013 data and generated metrics stay under ignored `data/raw/`
and `data/derived/`. Preserve the BBBC013 attribution in public-facing
documentation.
