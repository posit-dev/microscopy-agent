from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from chatlas import Turn

from agent import CommonsChatAdapter


class FakeCommons:
    def __init__(self) -> None:
        self.turns: list[Turn[Any]] = []
        self.calls: list[tuple[Any, ...]] = []
        self.client = SimpleNamespace(conversation_id=None)

    def get_turns(self) -> list[Turn[Any]]:
        return list(self.turns)

    def set_turns(self, turns: list[Turn[Any]]) -> None:
        self.turns = list(turns)

    async def stream_async(self, *args: Any, **kwargs: Any):
        self.calls.append(args)
        self.turns.append(Turn(args[0], role="user"))
        self.turns.append(Turn("Runtime response", role="assistant"))

        async def chunks():
            yield "Runtime response"

        return chunks()


def _saved_turn(text: str, role: str) -> dict[str, Any]:
    return Turn(text, role=role).model_dump(mode="json")


def test_adapter_restores_history_lazily_and_enriches_new_turn() -> None:
    fake = FakeCommons()
    constructions = 0

    def factory():
        nonlocal constructions
        constructions += 1
        return fake

    adapter = CommonsChatAdapter(
        agent_factory=factory,
        inventory=lambda: "- upload-1: Runtime sample",
    )
    adapter.set_turns(
        [
            _saved_turn("Earlier question", "user"),
            _saved_turn("Earlier answer", "assistant"),
        ]
    )
    adapter.conversation_id = "conversation-123"

    assert constructions == 0

    async def collect() -> list[str]:
        stream = await adapter.stream_async("Analyze the upload.", content="all")
        return [chunk async for chunk in stream]

    assert asyncio.run(collect()) == ["Runtime response"]
    assert constructions == 1
    assert fake.client.conversation_id == "conversation-123"
    assert len(fake.turns) == 4
    assert "<application-upload-inventory>" in fake.calls[0][0]
    assert "upload-1" in fake.calls[0][0]

    saved = adapter.get_turns()
    assert [turn["role"] for turn in saved] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]


def test_page_chat_combines_history_and_upload_controls() -> None:
    from app import app_ui

    markup = str(app_ui)
    assert "shiny-chat-history" in markup
    assert 'id="gfp_upload"' in markup
    assert 'id="dna_upload"' in markup
