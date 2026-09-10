from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterable, Sequence
from typing import Any

import commons
import pytest
from chatlas import Chat, ContentToolRequest, Turn
from chatlas._provider import Provider
from chatlas._turn import AssistantTurn
from chatlas.types import Content, ContentText, ModelInfo
from commons._provenance import TAG_EXTRA_KEY

from measures import microscopy as microscopy_measures
from measures.results import ScientificImageResult


class ScriptedProvider(Provider):
    """Exercise the real chatlas tool loop without a network model call."""

    def __init__(self, responses: Iterable[Sequence[Content]]) -> None:
        super().__init__(name="scripted", model="scripted-test")
        self.responses = [list(response) for response in responses]

    def _next(self) -> list[Content]:
        return self.responses.pop(0)

    async def chat_perform_async(
        self,
        *,
        stream: bool,
        turns: list[Turn],
        tools: Any,
        data_model: Any,
        kwargs: Any,
    ) -> AsyncIterator[Content]:
        response = self._next()

        async def chunks() -> AsyncIterator[Content]:
            for chunk in response:
                yield chunk

        return chunks()

    def chat_perform(
        self,
        *,
        stream: bool,
        turns: list[Turn],
        tools: Any,
        data_model: Any,
        kwargs: Any,
    ) -> Iterable[Content]:
        return self._next()

    def stream_merge_chunks(self, completion: Any, chunk: Any) -> list[Content]:
        return [*(completion or []), chunk]

    def stream_content(
        self,
        chunk: Any,
        completion: Any,
        turns: Sequence[Turn] = (),
    ) -> Sequence[Content]:
        return [chunk]

    def stream_turn(
        self,
        completion: Any,
        has_data_model: bool,
        turns: Sequence[Turn] = (),
    ) -> AssistantTurn[Any]:
        return AssistantTurn(list(completion or []))

    def value_turn(
        self,
        completion: Any,
        has_data_model: bool,
        turns: Sequence[Turn] = (),
    ) -> AssistantTurn[Any]:
        return AssistantTurn(list(completion or []))

    def value_tokens(self, completion: Any) -> tuple[int, int, int] | None:
        return None

    def token_count(
        self,
        turns: list[Turn],
        *,
        tools: Any,
        data_model: Any,
    ) -> int:
        return 0

    async def token_count_async(
        self,
        turns: list[Turn],
        *,
        tools: Any,
        data_model: Any,
    ) -> int:
        return 0

    def translate_model_params(self, params: Any) -> Any:
        return {}

    def supported_model_params(self) -> set[Any]:
        return set()

    def list_models(self) -> list[ModelInfo]:
        return []


def test_measure_image_is_streamed_with_verified_provenance() -> None:
    if not (
        microscopy_measures.RAW_DIR / "BBBC013_v1_platemap_all.txt"
    ).exists():
        pytest.skip("BBBC013 data has not been downloaded.")

    client = Chat(
        provider=ScriptedProvider(
            [
                [
                    ContentToolRequest(
                        id="call-annotate",
                        name="call_measure",
                        arguments={
                            "name": "annotate_well",
                            "arguments": '{"well":"A01"}',
                        },
                    )
                ],
                [ContentText(text="The annotated well is shown above.")],
            ]
        )
    )
    agent = commons.Commons(
        client,
        commons.data_source(wells=microscopy_measures.metadata_table()),
        semantic_layer=commons.semantic_layer(microscopy_measures),
    )

    async def collect() -> list[Any]:
        return [
            chunk
            async for chunk in await agent.stream_async(
                "Annotate well A01.",
                content="all",
            )
        ]

    chunks = asyncio.run(collect())
    image_results = [
        chunk for chunk in chunks if isinstance(chunk, ScientificImageResult)
    ]

    assert len(image_results) == 1
    assert image_results[0].extra[TAG_EXTRA_KEY] is commons.Tag.A
    assert any(
        isinstance(chunk, str)
        and '<shiny-aside label="Verified answer"' in chunk
        for chunk in chunks
    )
