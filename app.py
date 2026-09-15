"""Shiny chat app for the Commons microscopy demo."""

from __future__ import annotations

from pathlib import Path

import commons
from dotenv import load_dotenv
from shiny import App, reactive, render, ui
from shinychat import chat_sidebar, page_chat
from shinychat.types import HistoryOptions

from agent import build_agent
from microscopy.uploads import UPLOAD_LIBRARY

load_dotenv()

INITIAL_GREETING = (
    "Ask about FKHR nuclear signal, dose response, a BBBC013 well, or "
    "an image pair from the upload library.\n\n"
    "Try one of these:\n\n"
    "- <span class='suggestion'>What happens as we increase the Wortmannin "
    "dose?</span>\n"
    "- <span class='suggestion'>How does a responding well compare with an "
    "untreated one?</span>\n"
    "- <span class='suggestion'>How does LY294002 compare?</span>\n"
    "- <span class='suggestion'>What uploaded samples can you analyze?</span>\n"
)

UPLOAD_ACCEPT = [".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"]


def upload_form() -> ui.Tag:
    """Build the upload controls shown in the "Add microscopy data" dialog."""
    return ui.div(
        ui.p(
            "Add a matching GFP and DNA image pair. Samples are stored "
            "permanently and receive an ID the agent can use.",
            class_="text-body-secondary small",
        ),
        ui.input_text(
            "sample_name",
            "Sample name",
            placeholder="For example: patient-7 baseline",
        ),
        ui.input_file(
            "gfp_upload",
            "FKHR-GFP channel",
            accept=UPLOAD_ACCEPT,
            button_label="Choose file",
            placeholder="None selected",
        ),
        ui.input_file(
            "dna_upload",
            "DNA channel",
            accept=UPLOAD_ACCEPT,
            button_label="Choose file",
            placeholder="None selected",
        ),
        ui.output_ui("upload_status"),
        class_="microscopy-upload-form",
    )


UPLOAD_SIDEBAR = chat_sidebar(
    ui.tags.style(
        """
        #chat-sidebar {
          --bs-border-radius: 0.375rem;
          --bs-border-radius-sm: 0.25rem;
        }

        .shiny-tool-card:has(.microscopy-image-result) {
          opacity: 1 !important;
        }

        /* Wide enough cards that the four greeting suggestions land 2x2
           instead of 3 + 1, narrow enough to keep two columns when the chat
           column shrinks. shinychat reads this custom property directly; it
           is not a Sass variable of commons.ui.theme(). */
        .shiny-chat-suggestion-list {
          --shiny-chat-suggestion-card-min-width: 200px;
        }

        /* Shiny's file input renders a full-size button plus a readonly
           field, which towers over the text input above it. Size them like
           the sample-name field so the form sits on one scale. */
        .microscopy-upload-form .btn-file,
        .microscopy-upload-form .input-group .form-control {
          padding: 0.375rem 0.75rem;
          font-size: 0.9375rem;
          line-height: 1.5;
        }
        """
    ),
    ui.h6(
        "Available to the agent",
        class_="text-body-secondary text-uppercase fw-semibold small mb-2",
    ),
    ui.input_action_button(
        "open_upload",
        "Add microscopy data…",
        # The sidebar panel is a flex column, so without this the button
        # stretches to the full sidebar width.
        class_="btn-outline-primary align-self-start btn-sm px-4",
    ),
    ui.output_ui("upload_inventory"),
    history=True,
    width=360,
    open="open",
)

app_ui = page_chat(
    "Commons microscopy",
    id="chat",
    sidebar=UPLOAD_SIDEBAR,
    greeting=INITIAL_GREETING,
    placeholder="Ask about wells, doses, or uploads…",
    allow_attachments=False,
    window_title="Commons microscopy demo",
    theme=commons.ui.theme(),
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
    commons.ui.server(
        "chat",
        build_agent(),
        greeting=INITIAL_GREETING,
        history=HistoryOptions(title=None),
        on_error="actual",
    )
    upload_notice = reactive.value(None)
    inventory_version = reactive.value(0)
    saved_pair = reactive.value(None)

    @reactive.effect
    @reactive.event(input.open_upload)
    def _open_upload() -> None:
        upload_notice.set(None)
        ui.modal_show(
            ui.modal(
                upload_form(),
                title="Add microscopy data",
                easy_close=True,
                footer=ui.TagList(
                    ui.modal_button("Cancel"),
                    ui.input_action_button(
                        "save_upload",
                        "Add to library",
                        class_="btn-primary",
                    ),
                ),
            )
        )

    @reactive.effect
    @reactive.event(input.gfp_upload, input.dna_upload, ignore_init=True)
    def _clear_notice() -> None:
        # Choosing a file answers whatever the last complaint was about.
        upload_notice.set(None)

    @reactive.effect
    @reactive.event(input.save_upload)
    def _save_upload() -> None:
        gfp_files = input.gfp_upload()
        dna_files = input.dna_upload()
        if not gfp_files or not dna_files:
            upload_notice.set(("danger", "Choose both a GFP image and a DNA image."))
            return

        gfp = gfp_files[0]
        dna = dna_files[0]
        # Dismissing the dialog does not clear the file inputs server-side, so
        # a second visit would otherwise re-save the pair still sitting in
        # `input` when the button is clicked without choosing new files.
        pair = (gfp["datapath"], dna["datapath"])
        if pair == saved_pair.get():
            upload_notice.set(("danger", "Choose a new image pair to add."))
            return

        try:
            sample = UPLOAD_LIBRARY.register_pair(
                sample_name=input.sample_name() or Path(gfp["name"]).stem,
                gfp_path=gfp["datapath"],
                dna_path=dna["datapath"],
                gfp_filename=gfp["name"],
                dna_filename=dna["name"],
            )
        except Exception as error:
            upload_notice.set(("danger", str(error)))
            return

        saved_pair.set(pair)
        upload_notice.set(None)
        inventory_version.set(inventory_version.get() + 1)
        ui.modal_remove()
        ui.notification_show(
            f"Saved permanently as {sample.upload_id}. "
            "You can now refer to that ID in chat.",
            duration=8,
        )

    @render.ui
    def upload_status():
        notice = upload_notice.get()
        if notice is None:
            return None
        level, message = notice
        return ui.div(
            message,
            class_=f"alert alert-{level} py-2 px-3 mt-3 mb-0 small",
        )

    @render.ui
    def upload_inventory():
        inventory_version.get()
        samples = UPLOAD_LIBRARY.list_samples()
        if not samples:
            return ui.p(
                "No uploaded samples yet.",
                class_="text-body-secondary small",
            )
        return ui.TagList(
            *[
                ui.div(
                    ui.strong(sample.sample_name),
                    ui.tags.code(sample.upload_id, class_="d-block"),
                    ui.tags.small(
                        f"{sample.width}×{sample.height} · "
                        f"{sample.gfp_filename} + {sample.dna_filename}",
                        class_="text-body-secondary",
                    ),
                    class_="border rounded-2 p-2 mb-2",
                )
                for sample in samples[:20]
            ]
        )


app = App(app_ui, server)
