"""Serializable rich results for trusted microscopy measures."""

from __future__ import annotations

from typing import Any

from chatlas import ContentToolResult
from shiny import ui
from shinychat.types import ToolResultDisplay


class ScientificImageResult(ContentToolResult):
    """A model-readable result whose image lives in the tool display envelope."""


def scientific_image_result(
    *,
    value: Any,
    image_base64: str,
    alt_text: str,
    caption: str,
    extra: dict[str, Any] | None = None,
) -> ScientificImageResult:
    """Build an image result that survives shinychat history serialization."""
    display = ToolResultDisplay(
        html=ui.div(
            ui.img(
                src=f"data:image/png;base64,{image_base64}",
                alt=alt_text,
                style="display: block; width: 100%; height: auto;",
            ),
            ui.p(
                caption,
                style=(
                    "margin: 0; padding: 0.75rem 0.9rem 0.85rem; "
                    "font-size: 0.82rem; line-height: 1.45; "
                    "color: var(--bs-secondary-color);"
                ),
            ),
            style=(
                "margin: 0.5rem 0 1rem; overflow: hidden; "
                "border: 1px solid var(--bs-border-color); "
                "border-radius: 0.75rem; background: var(--bs-body-bg);"
            ),
        ),
        full_screen=True,
        open=True,
        open_style="framed",
    )
    return ScientificImageResult(
        value=value,
        extra={**(extra or {}), "display": display},
    )
