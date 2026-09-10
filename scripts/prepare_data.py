#!/usr/bin/env python3
"""Prepare cached BBBC013 well and nucleus metrics."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    from measures.microscopy import (
        NUCLEUS_METRICS_PATH,
        WELL_METRICS_PATH,
        _prepare_metrics,
    )

    metrics = _prepare_metrics()
    print(f"Wrote {len(metrics)} well rows to {WELL_METRICS_PATH}")
    print(f"Wrote per-nucleus rows to {NUCLEUS_METRICS_PATH}")


if __name__ == "__main__":
    main()
