"""Construct a fresh Commons microscopy agent."""

from __future__ import annotations

import os
from pathlib import Path

import chatlas
import commons

from measures import microscopy as microscopy_measures
from measures import uploads as upload_measures
from microscopy.dataset import build_well_metadata
from microscopy.uploads import UPLOAD_LIBRARY

PROJECT_ROOT = Path(__file__).resolve().parent


def build_agent() -> commons.Commons:
    """Build one session-local Commons agent."""
    provider_model = os.getenv("CHATLAS_CHAT_PROVIDER_MODEL")
    if not provider_model:
        raise RuntimeError(
            "Set CHATLAS_CHAT_PROVIDER_MODEL to a chatlas provider/model before "
            "starting the app."
        )

    metadata = build_well_metadata(PROJECT_ROOT / "data" / "raw")
    return commons.Commons(
        chatlas.ChatAuto(provider_model),
        {
            "wells": commons.data_source(wells=metadata),
            "uploads": commons.data_source(
                UPLOAD_LIBRARY.engine,
                tables=["uploads"],
            ),
        },
        semantic_layer=commons.semantic_layer(
            microscopy_measures,
            upload_measures,
        ),
        context_layer=commons.context_layer(
            files=[PROJECT_ROOT / "context" / "assay.md"]
        ),
        instructions=str(PROJECT_ROOT / "instructions.md"),
    )
