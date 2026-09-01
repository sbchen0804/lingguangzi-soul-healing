"""Render PDF pages to deterministic PNG files using Poppler's pdftoppm."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

from PIL import Image
from pypdf import PdfReader


def _resolve_pdftoppm() -> Path:
    """Find pdftoppm on PATH, then in configured/bundled runtimes."""
    on_path = shutil.which("pdftoppm")
    if on_path:
        return Path(on_path)

    candidates: list[Path] = []
    configured = os.environ.get("POPPLER_BIN") or os.environ.get("POPPLER_PATH")
    if configured:
        configured_path = Path(configured)
        candidates.append(
            configured_path / "pdftoppm.exe"
            if configured_path.is_dir()
            else configured_path
        )

    # Codex's bundled runtime is the supported local fallback on Windows.
    candidates.extend(
        [
            Path.home()
            / ".cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe",
            Path.home()
            / ".cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/pdftoppm.exe",
            Path.home()
            / ".cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/pdftoppm.exe",
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "pdftoppm was not found on PATH or in the configured/bundled Poppler runtime"
    )


def render_pdf_pages(pdf: Path, output: Path, prefix: str) -> list[dict]:
    """Render every page of *pdf* and return ordered page metadata."""
    pdf = Path(pdf)
    output = Path(output)
    if not pdf.is_file():
        raise FileNotFoundError(pdf)
    if not prefix:
        raise ValueError("prefix must not be empty")

    page_count = len(PdfReader(str(pdf)).pages)
    if page_count < 1:
        raise ValueError(f"PDF has no pages: {pdf}")

    output.mkdir(parents=True, exist_ok=True)
    render_prefix = output / f".{prefix}-render"
    command = [
        str(_resolve_pdftoppm()),
        "-png",
        "-r",
        "144",
        "-f",
        "1",
        "-l",
        str(page_count),
        str(pdf),
        str(render_prefix),
    ]
    completed = subprocess.run(command, check=False, shell=False, capture_output=True, text=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"pdftoppm failed (exit {completed.returncode}): {detail}")

    pages: list[dict] = []
    for page_number in range(1, page_count + 1):
        source = Path(f"{render_prefix}-{page_number}.png")
        if not source.exists():
            raise RuntimeError(f"missing rendered PDF page {page_number}")
        if source.stat().st_size == 0:
            raise RuntimeError(f"empty rendered PDF page {page_number}")

        destination = output / f"{prefix}-page-{page_number:02d}.png"
        source.replace(destination)
        try:
            with Image.open(destination) as image:
                width, height = image.size
                image.load()
        except Exception as exc:
            raise RuntimeError(f"invalid rendered PDF page {page_number}") from exc
        if width < 100 or height < 100:
            raise RuntimeError(
                f"rendered PDF page {page_number} is smaller than 100x100"
            )
        pages.append(
            {"path": str(destination), "page": page_number, "width": width, "height": height}
        )
    return pages
