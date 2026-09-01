"""Deterministically inventory a chapter source directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
import sys

try:
    from chapter_types import write_json
except ImportError:  # pragma: no cover - supports running this file directly
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from chapter_types import write_json


SUPPORTED = {".png", ".jpg", ".jpeg", ".pdf", ".docx", ".txt", ".mp3", ".m4a", ".mp4"}
_ZH_CHAPTER_RE = re.compile(r"第\s*(\d+)\s*章")
_EN_CHAPTER_RE = re.compile(r"chapter[-_ ]?(\d+)", re.IGNORECASE)


def _normalize_path(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("\\", "/"))


def role_candidates(relative_path: str) -> list[str]:
    """Return conservative candidate roles inferred from folder and suffix."""
    parts = relative_path.split("/", 1)
    if len(parts) != 2:
        return ["unknown"]
    folder, suffix = parts[0], Path(relative_path).suffix.lower()
    if folder == "原圖文" and suffix in {".png", ".jpg", ".jpeg"}:
        return ["original.cover"]
    if folder == "原圖文" and suffix == ".pdf":
        return ["original.pdf"]
    if folder == "詩歌創作" and suffix in {".mp3", ".m4a"}:
        return ["song.audio"]
    if folder == "詩歌創作" and suffix in {".docx", ".pdf", ".txt"}:
        return ["song.lyrics_source"]
    if folder.startswith("精煉篇"):
        return [
            "refined.image" if suffix in {".png", ".jpg", ".jpeg"} else
            "refined.document" if suffix == ".pdf" else
            "refined.audio" if suffix in {".mp3", ".m4a"} else
            "refined.video" if suffix == ".mp4" else "unknown"
        ]
    return ["unknown"]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory_digest(files: list[dict]) -> str:
    canonical = []
    seen: set[str] = set()
    for item in files:
        path = _normalize_path(item["path"])
        if path in seen:
            raise ValueError(f"normalized path collision: {path}")
        seen.add(path)
        canonical.append({"path": path, "size": item["size"], "sha256": item["sha256"]})
    canonical.sort(key=lambda item: item["path"])
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _chapter_number(root: Path) -> int:
    markers = _ZH_CHAPTER_RE.findall(root.name) + _EN_CHAPTER_RE.findall(root.name)
    if len(markers) != 1:
        raise ValueError(f"cannot determine chapter number from directory: {root}")
    return int(markers[0])


def scan_chapter(root: Path) -> dict:
    root = Path(root)
    if not root.is_dir():
        raise ValueError(f"chapter source directory does not exist: {root}")
    files = []
    normalized_paths: set[str] = set()
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED:
            continue
        relative = _normalize_path(path.relative_to(root).as_posix())
        if relative in normalized_paths:
            raise ValueError(f"normalized path collision: {relative}")
        normalized_paths.add(relative)
        stat = path.stat()
        candidates = role_candidates(relative)
        files.append({
            "path": relative,
            "size": stat.st_size,
            "modified_time": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            "sha256": _sha256(path),
            "role_candidates": candidates,
        })
    files.sort(key=lambda item: item["path"])
    digest = inventory_digest(files)
    return {
        "chapter": _chapter_number(root),
        "files": files,
        "inventory_digest": digest,
        "issues": [],
    }


def _lock_from_inventory(inventory: dict) -> dict:
    return {
        "chapter": inventory["chapter"],
        "inventory_digest": inventory["inventory_digest"],
        "files": [
            {
                "path": item["path"],
                "size": item["size"],
                "modified_time": item["modified_time"],
                "sha256": item["sha256"],
                "role": item["role_candidates"][0] if len(item["role_candidates"]) == 1 else "unknown",
            }
            for item in inventory["files"]
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--write", action="store_true", help="write chapter.inventory.json and chapter.lock.json")
    args = parser.parse_args(argv)
    inventory = scan_chapter(args.root)
    if args.write:
        write_json(args.root / "chapter.inventory.json", inventory)
        write_json(args.root / "chapter.lock.json", _lock_from_inventory(inventory))
    else:
        print(json.dumps(inventory, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
