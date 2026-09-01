"""Render PDF pages to deterministic PNG files using Poppler's pdftoppm."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile

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
    if not isinstance(prefix, str) or not prefix:
        raise ValueError("prefix must be a non-empty filename stem")
    if prefix in {".", ".."} or "/" in prefix or "\\" in prefix:
        raise ValueError("prefix must be a filename stem without path separators")
    if any(character in '<>:"|?*' for character in prefix):
        raise ValueError("prefix contains a Windows-forbidden filename character")
    if any(ord(character) < 32 or ord(character) == 127 for character in prefix):
        raise ValueError("prefix contains a control character")

    page_count = len(PdfReader(str(pdf)).pages)
    if page_count < 1:
        raise ValueError(f"PDF has no pages: {pdf}")

    output.mkdir(parents=True, exist_ok=True)
    output_resolved = output.resolve()
    destinations = [output_resolved / f"{prefix}-page-{n:02d}.png" for n in range(1, page_count + 1)]
    if any(destination.parent != output_resolved for destination in destinations):
        raise ValueError("prefix resolves outside output directory")
    collisions = [destination for destination in destinations if destination.exists()]
    if collisions:
        raise FileExistsError(f"render output already exists: {collisions[0]}")

    temporary = Path(tempfile.mkdtemp(prefix=".pdf-render-", dir=output_resolved))
    try:
        render_prefix = temporary / prefix
        command = [
            str(_resolve_pdftoppm()),
            "-png", "-r", "144", "-f", "1", "-l", str(page_count),
            str(pdf), str(render_prefix),
        ]
        completed = subprocess.run(command, check=False, shell=False, capture_output=True, text=True)
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(f"pdftoppm failed (exit {completed.returncode}): {detail}")

        validated: list[dict] = []
        sources: list[Path] = []
        source_number_width = len(str(page_count))
        for page_number in range(1, page_count + 1):
            source = Path(f"{render_prefix}-{page_number:0{source_number_width}d}.png")
            if not source.exists():
                raise RuntimeError(f"missing rendered PDF page {page_number}")
            if source.stat().st_size == 0:
                raise RuntimeError(f"empty rendered PDF page {page_number}")
            try:
                with Image.open(source) as image:
                    width, height = image.size
                    image.load()
            except Exception as exc:
                raise RuntimeError(f"invalid rendered PDF page {page_number}") from exc
            if width < 100 or height < 100:
                raise RuntimeError(f"rendered PDF page {page_number} is smaller than 100x100")
            sources.append(source)
            validated.append({"path": str(destinations[page_number - 1]), "page": page_number, "width": width, "height": height})

        # Promote only after every page is valid, and never overwrite a collision.
        promoted: list[Path] = []
        try:
            for source, destination in zip(sources, destinations):
                if destination.exists():
                    raise FileExistsError(f"render output already exists: {destination}")
                os.link(source, destination)
                promoted.append(destination)
                source.unlink()
        except Exception:
            for destination in promoted:
                try:
                    destination.unlink()
                except FileNotFoundError:
                    pass
            raise
        return validated
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
