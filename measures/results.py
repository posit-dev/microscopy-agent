"""Rich measure results that remain model-readable and render as images."""

from __future__ import annotations

from chatlas import ContentToolResult
from shiny import ui
from shinychat import message_content, message_content_chunk
from shinychat.types import ChatMessage


class ScientificImageResult(ContentToolResult):
    """A textual tool result with a separately rendered trusted PNG."""

    image_base64: str
    alt_text: str
    caption: str


def _result_ui(result: ScientificImageResult) -> ChatMessage:
    return ChatMessage(
        content=ui.div(
            ui.img(
                src=f"data:image/png;base64,{result.image_base64}",
                alt=result.alt_text,
                style="display: block; width: 100%; height: auto;",
            ),
            ui.p(
                result.caption,
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
        )
    )


@message_content.register
def _(result: ScientificImageResult) -> ChatMessage:
    return _result_ui(result)


@message_content_chunk.register
def _(result: ScientificImageResult) -> ChatMessage:
    return _result_ui(result)
