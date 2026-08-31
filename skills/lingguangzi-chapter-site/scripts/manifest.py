"""Draft, validate, confirm, and invalidate chapter manifests."""

from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
from uuid import uuid4

try:
    from chapter_types import Issue, read_json, write_json
except ImportError:  # pragma: no cover - supports running this file directly
    from .chapter_types import Issue, read_json, write_json


REQUIRED_CODES = {
    "missing_required_field",
    "missing_source_file",
    "duplicate_id",
    "duplicate_order",
    "unmapped_file",
    "inventory_mismatch",
    "visual_brief_incomplete",
}

_VISUAL_FIELDS = (
    "style_family",
    "concept",
    "composition",
    "palette",
    "mood",
    "distinctive_elements",
    "avoid",
)


def draft_manifest(inventory: dict) -> dict:
    """Create an editable, intentionally incomplete manifest from an inventory."""
    return {
        "schema_version": 1,
        "revision": 0,
        "status": "draft",
        "inventory_digest": inventory["inventory_digest"],
        "chapter": inventory["chapter"],
        "title": "",
        "subtitle": "",
        "theme": {"keywords": [], "visual_notes": ""},
        "visual": {},
        "original": {},
        "songs": [],
        "refined": {"title": "找回生命的靈魂處方", "items": []},
        "sharing": {},
        "excluded_files": [],
    }


def _is_present(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return value is not None


def _issue(code: str, message: str, path: str | None = None) -> Issue:
    return Issue(code, "blocking", message, path)


def _required(issues: list[Issue], container: object, field: str, label: str) -> object | None:
    value = container.get(field) if isinstance(container, dict) else None
    if not _is_present(value):
        issues.append(_issue("missing_required_field", f"缺少必填欄位：{label}", label))
        return None
    return value


def _source_paths(manifest: dict) -> list[str]:
    paths: list[str] = []
    original = manifest.get("original", {})
    if isinstance(original, dict):
        paths.extend(value for key in ("cover", "pdf") if isinstance((value := original.get(key)), str) and value)
    for song in manifest.get("songs", []):
        if isinstance(song, dict):
            paths.extend(value for key in ("audio", "lyrics_source") if isinstance((value := song.get(key)), str) and value)
    refined = manifest.get("refined", {})
    if isinstance(refined, dict):
        for item in refined.get("items", []):
            if isinstance(item, dict) and isinstance(item.get("file"), str) and item["file"]:
                paths.append(item["file"])
    return paths


def _validate_required_fields(manifest: dict, issues: list[Issue]) -> None:
    for field in ("schema_version", "revision", "status", "inventory_digest", "chapter", "title", "subtitle", "theme", "visual", "original", "songs", "refined", "sharing", "excluded_files"):
        value = manifest.get(field)
        if field in {"songs", "excluded_files"}:
            if not isinstance(value, list):
                issues.append(_issue("missing_required_field", f"缺少必填欄位：{field}", field))
        elif field == "sharing":
            if not isinstance(value, dict):
                issues.append(_issue("missing_required_field", f"缺少必填欄位：{field}", field))
        elif not _is_present(value):
            issues.append(_issue("missing_required_field", f"缺少必填欄位：{field}", field))

    original = manifest.get("original")
    _required(issues, original, "cover", "original.cover")
    _required(issues, original, "pdf", "original.pdf")
    refined = manifest.get("refined")
    _required(issues, refined, "title", "refined.title")
    if not isinstance(refined, dict) or not isinstance(refined.get("items"), list):
        issues.append(_issue("missing_required_field", "缺少必填欄位：refined.items", "refined.items"))

    for index, song in enumerate(manifest.get("songs", [])):
        for field in ("id", "title", "audio", "lyrics_source", "order"):
            _required(issues, song, field, f"songs[{index}].{field}")
    if isinstance(refined, dict):
        for index, item in enumerate(refined.get("items", [])):
            for field in ("type", "role", "title", "file", "order"):
                _required(issues, item, field, f"refined.items[{index}].{field}")


def _validate_duplicates(manifest: dict, issues: list[Issue]) -> None:
    songs = [song for song in manifest.get("songs", []) if isinstance(song, dict)]
    ids = [song.get("id") for song in songs if _is_present(song.get("id"))]
    if len(ids) != len(set(ids)):
        issues.append(_issue("duplicate_id", "詩歌 id 不得重複", "songs"))
    song_orders = [song.get("order") for song in songs if _is_present(song.get("order"))]
    if len(song_orders) != len(set(song_orders)):
        issues.append(_issue("duplicate_order", "詩歌 order 不得重複", "songs"))

    refined = manifest.get("refined", {})
    items = refined.get("items", []) if isinstance(refined, dict) else []
    orders = [item.get("order") for item in items if isinstance(item, dict) and _is_present(item.get("order"))]
    if len(orders) != len(set(orders)):
        issues.append(_issue("duplicate_order", "精煉項目 order 不得重複", "refined.items"))


def _validate_visual(manifest: dict, issues: list[Issue]) -> None:
    visual = manifest.get("visual")
    missing = [field for field in _VISUAL_FIELDS if not isinstance(visual, dict) or not _is_present(visual.get(field))]
    if missing:
        issues.append(_issue("visual_brief_incomplete", f"視覺 DNA 不完整：{', '.join(missing)}", "visual"))


def _validate_source_mapping(manifest: dict, inventory: dict, issues: list[Issue]) -> None:
    inventory_paths = {item["path"] for item in inventory.get("files", []) if isinstance(item, dict) and isinstance(item.get("path"), str)}
    mapped = _source_paths(manifest)
    excluded = manifest.get("excluded_files", [])
    excluded = excluded if isinstance(excluded, list) else []
    declared = mapped + [path for path in excluded if isinstance(path, str)]

    for path in declared:
        if path not in inventory_paths:
            issues.append(_issue("missing_source_file", f"來源檔案不存在：{path}", path))
    for path in sorted(inventory_paths):
        count = declared.count(path)
        if count != 1:
            issues.append(_issue("unmapped_file", f"來源檔案必須剛好對應一次或明確排除：{path}", path))


def validate_manifest(manifest: dict, inventory: dict) -> list[Issue]:
    """Return all blocking consistency problems for a manifest and inventory."""
    issues: list[Issue] = []
    if not isinstance(manifest, dict):
        return [_issue("missing_required_field", "manifest 必須是物件")]
    _validate_required_fields(manifest, issues)
    _validate_duplicates(manifest, issues)
    _validate_visual(manifest, issues)
    _validate_source_mapping(manifest, inventory, issues)
    if manifest.get("inventory_digest") != inventory.get("inventory_digest"):
        issues.append(_issue("inventory_mismatch", "來源目錄指紋與 manifest 不一致", "inventory_digest"))
    return issues


def confirm_manifest(path: Path, inventory: dict) -> dict:
    """Atomically persist a validated confirmed manifest with a new revision."""
    path = Path(path)
    manifest = read_json(path)
    issues = validate_manifest(manifest, inventory)
    blocking = [issue for issue in issues if issue.severity == "blocking"]
    if blocking:
        raise ValueError("manifest has blocking issues: " + ", ".join(issue.code for issue in blocking))
    confirmed = deepcopy(manifest)
    confirmed["status"] = "confirmed"
    confirmed["revision"] = int(confirmed.get("revision", 0)) + 1
    confirmed["inventory_digest"] = inventory["inventory_digest"]
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        write_json(temporary, confirmed)
        temporary.replace(path)
    finally:
        if temporary.exists():
            os.unlink(temporary)
    return confirmed


def invalidate_if_changed(manifest: dict, inventory: dict) -> dict:
    """Return a revised draft when the scanned source inventory has changed."""
    changed = deepcopy(manifest)
    current_digest = inventory.get("inventory_digest")
    if changed.get("status") == "confirmed" and changed.get("inventory_digest") != current_digest:
        changed["status"] = "draft"
        changed["revision"] = int(changed.get("revision", 0)) + 1
        changed["inventory_digest"] = current_digest
    return changed
