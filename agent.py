"""Construct a fresh Commons microscopy agent."""

from __future__ import annotations

import copy
import os
from collections.abc import AsyncGenerator, Callable, Sequence
from pathlib import Path
from typing import Any, Literal

import chatlas
import commons
from chatlas import StreamController, Turn
from chatlas.types import Content

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


class CommonsChatAdapter:
    """Lazy shinychat client preserving Commons projection and saved turns."""

    def __init__(
        self,
        agent_factory: Callable[[], commons.Commons] = build_agent,
        inventory: Callable[[], str] = UPLOAD_LIBRARY.prompt_inventory,
    ) -> None:
        self._agent_factory = agent_factory
        self._inventory = inventory
        self._agent: commons.Commons | None = None
        self._saved_turns: list[dict[str, Any]] = []
        self.conversation_id: str | None = None

    def _ensure_agent(self) -> commons.Commons:
        if self._agent is None:
            self._agent = self._agent_factory()
            if self._saved_turns:
                self._agent.set_turns(
                    [Turn.model_validate(turn) for turn in self._saved_turns]
                )
        client = self._agent.client
        if hasattr(client, "conversation_id"):
            client.conversation_id = self.conversation_id
        return self._agent

    @staticmethod
    def _serialize_turn(turn: Any) -> dict[str, Any]:
        if isinstance(turn, dict):
            return copy.deepcopy(turn)
        if hasattr(turn, "model_dump"):
            return turn.model_dump(
                mode="json",
                fallback=lambda value: str(value),
            )
        raise TypeError(f"Unsupported saved turn type: {type(turn).__name__}")

    def get_turns(self) -> list[dict[str, Any]]:
        """Return JSON-safe turns for shinychat's conversation store."""
        if self._agent is not None:
            self._saved_turns = [
                self._serialize_turn(turn) for turn in self._agent.get_turns()
            ]
        return copy.deepcopy(self._saved_turns)

    def set_turns(self, turns: Sequence[Any]) -> None:
        """Restore JSON turns from shinychat, building Commons only when needed."""
        self._saved_turns = [self._serialize_turn(turn) for turn in turns]
        if self._agent is not None:
            self._agent.set_turns(
                [Turn.model_validate(turn) for turn in self._saved_turns]
            )

    async def stream_async(
        self,
        *args: Content | str,
        content: Literal["text", "all"] = "text",
        echo: Any = "none",
        kwargs: Any = None,
        controller: StreamController | None = None,
    ) -> AsyncGenerator[str | Content, None]:
        """Enrich the user turn with upload state and stream through Commons."""
        if not args or not isinstance(args[0], str):
            raise ValueError("The first chat input must be user text.")
        user_input, *attachments = args
        enriched_input = (
            f"{user_input}\n\n"
            "<application-upload-inventory>\n"
            f"{self._inventory()}\n"
            "</application-upload-inventory>\n"
            "The inventory above is current application state. Use its exact "
            "upload IDs when calling upload measures."
        )
        agent = self._ensure_agent()
        return await agent.stream_async(
            enriched_input,
            *attachments,
            content=content,
            echo=echo,
            kwargs=kwargs,
            controller=controller,
        )
