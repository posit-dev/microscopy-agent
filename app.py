"""Shiny chat app for the Commons microscopy demo."""

from __future__ import annotations

from shiny import App, ui
from shinychat import Chat, page_chat

from agent import build_agent

INITIAL_GREETING = ui.TagList(
    ui.p(
        "Ask about FKHR nuclear signal, dose response, or a specific "
        "BBBC013 well."
    ),
    ui.p(
        "Try: ",
        ui.tags.span(
            "What happens as we increase the Wortmannin dose?",
            class_="suggestion submit",
        ),
    ),
)

app_ui = page_chat(
    "Commons microscopy",
    id="chat",
    greeting=INITIAL_GREETING,
    placeholder="Ask about wells, treatments, or dose response…",
    window_title="Commons microscopy demo",
    footer=ui.div(
        "BBBC013 · U2OS FKHR-EGFP · illustrative analysis, not a validated "
        "assay. Images © Ilya Ravkin, CC BY 3.0.",
        style=(
            "padding: 0.35rem 1rem 0.6rem; text-align: center; "
            "font-size: 0.75rem; color: var(--bs-secondary-color);"
        ),
    ),
)


def server(input, output, session) -> None:
    chat = Chat("chat", on_error="actual")
    microscopy_agent = build_agent()

    @chat.on_user_submit
    async def _(user_input: str) -> None:
        response = await microscopy_agent.stream_async(user_input, content="all")
        await chat.append_message_stream(response)


app = App(app_ui, server)
