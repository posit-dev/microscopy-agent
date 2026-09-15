from __future__ import annotations

import commons
from chatlas import Chat


def test_commons_uses_chatlas_history_semantics() -> None:
    assert issubclass(commons.Commons, Chat)


def test_page_chat_combines_commons_theme_history_and_upload_controls() -> None:
    from app import app_ui

    markup = str(app_ui)
    assert "shiny-chat-history" in markup
    assert any(
        dependency.name == "commons-chat" for dependency in app_ui.get_dependencies()
    )
    assert "--bs-border-radius: 0.375rem" in markup
    assert ".shiny-tool-card:has(.microscopy-image-result)" in markup
    assert 'id="open_upload"' in markup


def test_upload_dialog_collects_both_channels() -> None:
    from app import upload_form

    markup = str(upload_form())
    assert 'id="gfp_upload"' in markup
    assert 'id="dna_upload"' in markup
    assert 'id="sample_name"' in markup


def test_greeting_offers_four_suggestion_cards() -> None:
    from app import INITIAL_GREETING

    items = [
        line
        for line in INITIAL_GREETING.splitlines()
        if line.startswith("- <span class='suggestion'")
    ]
    assert len(items) == 4
