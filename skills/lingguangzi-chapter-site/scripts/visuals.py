"""Validate and register distinct visual identities for chapter artwork."""

from __future__ import annotations

import json
from pathlib import Path

try:
    from chapter_types import Issue, write_json
except ImportError:  # pragma: no cover
    from .chapter_types import Issue, write_json


DIMENSIONS = ("concept", "composition", "palette", "distinctive_elements", "lighting")


def _normalized(value: object) -> object:
    if isinstance(value, list):
        return tuple(sorted(str(item).strip() for item in value if str(item).strip()))
    return str(value).strip() if value is not None else ""


def recent_visuals(registry: list[dict], count: int = 6) -> list[dict]:
    """Return the newest valid registry entries, ordered oldest to newest."""
    if count < 0:
        raise ValueError("count must be non-negative")
    valid = [item for item in registry if isinstance(item, dict) and isinstance(item.get("chapter"), int)]
    return sorted(valid, key=lambda item: item["chapter"])[-count:] if count else []


def visual_differences(current: dict, previous: dict) -> set[str]:
    """Return visual-DNA dimensions that materially differ."""
    return {field for field in DIMENSIONS if _normalized(current.get(field)) != _normalized(previous.get(field))}


def validate_visual_brief(current: dict, registry: list[dict]) -> list[Issue]:
    issues: list[Issue] = []
    if not isinstance(current, dict) or any(not _normalized(current.get(field)) for field in DIMENSIONS):
        return [Issue("visual_brief_incomplete", "blocking", "主视觉需包含概念、构图、色彩、独特元素与光线", "visual")]
    recent = recent_visuals(registry)
    if recent and len(visual_differences(current, recent[-1])) < 3:
        issues.append(Issue("visual_too_similar", "blocking", "与前一章至少需要三个视觉维度不同", "visual"))
    current_composition = _normalized(current.get("composition"))
    current_elements = _normalized(current.get("distinctive_elements"))
    if any(
        current_composition == _normalized(item.get("composition"))
        and current_elements == _normalized(item.get("distinctive_elements"))
        for item in recent
    ):
        issues.append(Issue("visual_too_similar", "blocking", "最近六章不可重复相同构图与核心元素", "visual"))
    return issues


def register_visual(registry_path: Path, entry: dict) -> None:
    """Atomically add or replace one chapter entry in the visual registry."""
    if not isinstance(entry, dict) or not isinstance(entry.get("chapter"), int):
        raise ValueError("visual registry entry requires an integer chapter")
    registry_path = Path(registry_path)
    try:
        existing = json.loads(registry_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        existing = []
    if not isinstance(existing, list):
        raise ValueError("visual registry must be a JSON array")
    merged = [item for item in existing if isinstance(item, dict) and item.get("chapter") != entry["chapter"]]
    merged.append(entry)
    merged.sort(key=lambda item: item.get("chapter", -1))
    temporary = registry_path.with_suffix(registry_path.suffix + ".tmp")
    try:
        write_json(temporary, {"entries": merged})
        payload = json.loads(temporary.read_text(encoding="utf-8"))["entries"]
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(registry_path)
    finally:
        temporary.unlink(missing_ok=True)
