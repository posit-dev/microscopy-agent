"""Persistent storage for user-supplied microscopy channel pairs."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import sqlalchemy
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UPLOAD_ROOT = PROJECT_ROOT / "data" / "uploads"
MAX_UPLOAD_BYTES = 64 * 1024 * 1024
MAX_IMAGE_PIXELS = 50_000_000


@dataclass(frozen=True)
class UploadedSample:
    """Public metadata for one persistent uploaded image pair."""

    upload_id: str
    sample_name: str
    gfp_filename: str
    dna_filename: str
    width: int
    height: int
    gfp_sha256: str
    dna_sha256: str
    created_at: str


def _slug(value: str) -> str:
    compact = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return compact[:40] or "sample"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inspect_image(path: Path) -> tuple[int, int, str]:
    if not path.is_file():
        raise ValueError(f"Uploaded file does not exist: {path.name}")
    if path.stat().st_size > MAX_UPLOAD_BYTES:
        raise ValueError(f"{path.name} exceeds the 64 MB upload limit.")

    with Image.open(path) as image:
        image.load()
        width, height = image.size
        image_format = (image.format or "").lower()

    if width * height > MAX_IMAGE_PIXELS:
        raise ValueError(f"{path.name} is too large to analyze safely.")
    if width < 2 or height < 2:
        raise ValueError(f"{path.name} is not a usable microscopy image.")
    if not image_format:
        raise ValueError(f"Could not determine the image format for {path.name}.")
    return width, height, image_format


def _extension(image_format: str) -> str:
    return {
        "jpeg": ".jpg",
        "tiff": ".tiff",
    }.get(image_format, f".{image_format}")


class UploadLibrary:
    """A permanent image library with a public inventory and private paths."""

    def __init__(self, root: str | Path = DEFAULT_UPLOAD_ROOT) -> None:
        self.root = Path(root).resolve()
        self.files_root = self.root / "files"
        self.root.mkdir(parents=True, exist_ok=True)
        self.files_root.mkdir(parents=True, exist_ok=True)
        database_path = self.root / "library.sqlite3"
        self.engine = sqlalchemy.create_engine(
            f"sqlite:///{database_path}",
            connect_args={"check_same_thread": False},
        )
        self._initialize()

    def _initialize(self) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                sqlalchemy.text(
                    """
                    CREATE TABLE IF NOT EXISTS uploads (
                        upload_id TEXT PRIMARY KEY,
                        sample_name TEXT NOT NULL,
                        gfp_filename TEXT NOT NULL,
                        dna_filename TEXT NOT NULL,
                        width INTEGER NOT NULL,
                        height INTEGER NOT NULL,
                        gfp_sha256 TEXT NOT NULL,
                        dna_sha256 TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
            )
            connection.execute(
                sqlalchemy.text(
                    """
                    CREATE TABLE IF NOT EXISTS upload_files (
                        upload_id TEXT PRIMARY KEY,
                        gfp_path TEXT NOT NULL,
                        dna_path TEXT NOT NULL,
                        FOREIGN KEY(upload_id) REFERENCES uploads(upload_id)
                    )
                    """
                )
            )

    def register_pair(
        self,
        *,
        sample_name: str,
        gfp_path: str | Path,
        dna_path: str | Path,
        gfp_filename: str | None = None,
        dna_filename: str | None = None,
    ) -> UploadedSample:
        """Validate, permanently copy, and register a two-channel sample."""
        gfp_source = Path(gfp_path)
        dna_source = Path(dna_path)
        gfp_width, gfp_height, gfp_format = _inspect_image(gfp_source)
        dna_width, dna_height, dna_format = _inspect_image(dna_source)
        if (gfp_width, gfp_height) != (dna_width, dna_height):
            raise ValueError(
                "The GFP and DNA images must have identical pixel dimensions."
            )

        gfp_hash = _sha256(gfp_source)
        dna_hash = _sha256(dna_source)
        pair_hash = hashlib.sha256(f"{gfp_hash}:{dna_hash}".encode()).hexdigest()
        resolved_name = sample_name.strip() or gfp_source.stem
        upload_id = f"{_slug(resolved_name)}-{pair_hash[:10]}"
        destination = self.files_root / upload_id
        destination.mkdir(parents=True, exist_ok=True)
        saved_gfp = destination / f"gfp{_extension(gfp_format)}"
        saved_dna = destination / f"dna{_extension(dna_format)}"
        shutil.copyfile(gfp_source, saved_gfp)
        shutil.copyfile(dna_source, saved_dna)

        created_at = datetime.now(UTC).isoformat()
        public_values = {
            "upload_id": upload_id,
            "sample_name": resolved_name,
            "gfp_filename": gfp_filename or gfp_source.name,
            "dna_filename": dna_filename or dna_source.name,
            "width": gfp_width,
            "height": gfp_height,
            "gfp_sha256": gfp_hash,
            "dna_sha256": dna_hash,
            "created_at": created_at,
        }
        with self.engine.begin() as connection:
            connection.execute(
                sqlalchemy.text(
                    """
                    INSERT INTO uploads (
                        upload_id, sample_name, gfp_filename, dna_filename,
                        width, height, gfp_sha256, dna_sha256, created_at
                    ) VALUES (
                        :upload_id, :sample_name, :gfp_filename, :dna_filename,
                        :width, :height, :gfp_sha256, :dna_sha256, :created_at
                    )
                    ON CONFLICT(upload_id) DO UPDATE SET
                        sample_name = excluded.sample_name,
                        gfp_filename = excluded.gfp_filename,
                        dna_filename = excluded.dna_filename,
                        width = excluded.width,
                        height = excluded.height,
                        gfp_sha256 = excluded.gfp_sha256,
                        dna_sha256 = excluded.dna_sha256,
                        created_at = excluded.created_at
                    """
                ),
                public_values,
            )
            connection.execute(
                sqlalchemy.text(
                    """
                    INSERT INTO upload_files (upload_id, gfp_path, dna_path)
                    VALUES (:upload_id, :gfp_path, :dna_path)
                    ON CONFLICT(upload_id) DO UPDATE SET
                        gfp_path = excluded.gfp_path,
                        dna_path = excluded.dna_path
                    """
                ),
                {
                    "upload_id": upload_id,
                    "gfp_path": str(saved_gfp.resolve()),
                    "dna_path": str(saved_dna.resolve()),
                },
            )
        return UploadedSample(**public_values)

    def list_samples(self) -> list[UploadedSample]:
        """Return all persistent samples, newest first."""
        with self.engine.connect() as connection:
            rows = connection.execute(
                sqlalchemy.text(
                    """
                    SELECT upload_id, sample_name, gfp_filename, dna_filename,
                           width, height, gfp_sha256, dna_sha256, created_at
                    FROM uploads
                    ORDER BY created_at DESC, upload_id
                    """
                )
            ).mappings()
            return [UploadedSample(**dict(row)) for row in rows]

    def prompt_inventory(self, limit: int = 30) -> str:
        """Describe persistent uploads for model context without private paths."""
        samples = self.list_samples()[:limit]
        if not samples:
            return "No uploaded microscopy samples are currently registered."
        lines = [
            (
                f"- {sample.upload_id}: {sample.sample_name}; "
                f"{sample.width}x{sample.height}; GFP file "
                f"{sample.gfp_filename}; DNA file {sample.dna_filename}"
            )
            for sample in samples
        ]
        return "Persistent uploaded microscopy samples:\n" + "\n".join(lines)


def fetch_upload(engine: sqlalchemy.Engine, upload_id: str) -> dict[str, Any]:
    """Resolve one model-visible upload ID to public metadata and private paths."""
    with engine.connect() as connection:
        row = connection.execute(
            sqlalchemy.text(
                """
                SELECT uploads.*, upload_files.gfp_path, upload_files.dna_path
                FROM uploads
                JOIN upload_files USING (upload_id)
                WHERE uploads.upload_id = :upload_id
                """
            ),
            {"upload_id": upload_id},
        ).mappings().one_or_none()
    if row is None:
        raise ValueError(
            f"Unknown upload ID {upload_id!r}. Call list_uploaded_samples first."
        )
    return dict(row)


UPLOAD_LIBRARY = UploadLibrary(
    os.environ.get("MICROSCOPY_UPLOAD_ROOT", DEFAULT_UPLOAD_ROOT)
)
