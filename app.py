"""Shiny chat app for the Commons microscopy demo."""

from __future__ import annotations

from pathlib import Path

import commons
from shiny import App, reactive, render, ui
from shinychat import chat_sidebar, page_chat
from shinychat.types import HistoryOptions

from agent import build_agent
from microscopy.uploads import UPLOAD_LIBRARY

INITIAL_GREETING = ui.TagList(
    ui.p(
        "Ask about FKHR nuclear signal, dose response, a BBBC013 well, or "
        "an image pair from the upload library."
    ),
    ui.p(
        "Try: ",
        ui.tags.span(
            "What happens as we increase the Wortmannin dose?",
            class_="suggestion submit",
        ),
    ),
)

UPLOAD_ACCEPT = [".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"]

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
        """
    ),
    ui.h4("Upload microscopy data"),
    ui.p(
        "Add a matching GFP and DNA image pair. Samples are stored permanently "
        "and receive an ID the agent can use.",
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
        button_label="Choose GFP image",
        placeholder="No GFP image selected",
    ),
    ui.input_file(
        "dna_upload",
        "DNA channel",
        accept=UPLOAD_ACCEPT,
        button_label="Choose DNA image",
        placeholder="No DNA image selected",
    ),
    ui.input_action_button(
        "save_upload",
        "Add to library",
        class_="btn-primary w-100",
    ),
    ui.output_ui("upload_status"),
    ui.hr(),
    ui.h5("Available to the agent"),
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
    placeholder="Ask about wells, treatments, dose response, or uploads…",
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

    @reactive.effect
    @reactive.event(input.save_upload)
    def _save_upload() -> None:
        gfp_files = input.gfp_upload()
        dna_files = input.dna_upload()
        if not gfp_files or not dna_files:
            upload_notice.set(
                ("danger", "Choose both a GFP image and a DNA image.")
            )
            return

        gfp = gfp_files[0]
        dna = dna_files[0]
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

        upload_notice.set(
            (
                "success",
                f"Saved permanently as {sample.upload_id}. "
                "You can now refer to that ID in chat.",
            )
        )
        inventory_version.set(inventory_version.get() + 1)

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
