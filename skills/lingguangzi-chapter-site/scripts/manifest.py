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


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _issue(code: str, message: str, path: str | None = None) -> Issue:
    return Issue(code, "blocking", message, path)


def _schema_error(issues: list[Issue], label: str) -> None:
    issues.append(_issue("missing_required_field", f"欄位缺少或格式錯誤：{label}", label))


def _source_paths(manifest: dict) -> list[str]:
    paths: list[str] = []
    original = manifest.get("original", {})
    if isinstance(original, dict):
        paths.extend(value for key in ("cover", "pdf") if isinstance((value := original.get(key)), str) and value)
    songs = manifest.get("songs")
    for song in songs if isinstance(songs, list) else []:
        if isinstance(song, dict):
            paths.extend(value for key in ("audio", "lyrics_source") if isinstance((value := song.get(key)), str) and value)
    refined = manifest.get("refined", {})
    if isinstance(refined, dict):
        items = refined.get("items")
        for item in items if isinstance(items, list) else []:
            if isinstance(item, dict) and isinstance(item.get("file"), str) and item["file"]:
                paths.append(item["file"])
    return paths


def _validate_required_fields(manifest: dict, issues: list[Issue]) -> None:
    if not _is_int(manifest.get("schema_version")):
        _schema_error(issues, "schema_version")
    if not _is_int(manifest.get("revision")):
        _schema_error(issues, "revision")
    if manifest.get("status") not in {"draft", "confirmed"}:
        _schema_error(issues, "status")
    if not _is_string(manifest.get("inventory_digest")):
        _schema_error(issues, "inventory_digest")
    if not _is_int(manifest.get("chapter")):
        _schema_error(issues, "chapter")
    for field in ("title", "subtitle"):
        if not _is_string(manifest.get(field)):
            _schema_error(issues, field)

    theme = manifest.get("theme")
    if not isinstance(theme, dict):
        _schema_error(issues, "theme")
    else:
        keywords = theme.get("keywords")
        if not isinstance(keywords, list) or not all(_is_string(value) for value in keywords):
            _schema_error(issues, "theme.keywords")
        if "visual_notes" in theme and not isinstance(theme["visual_notes"], str):
            _schema_error(issues, "theme.visual_notes")

    original = manifest.get("original")
    if not isinstance(original, dict):
        _schema_error(issues, "original")
    else:
        for field in ("cover", "pdf"):
            if not _is_string(original.get(field)):
                _schema_error(issues, f"original.{field}")

    songs = manifest.get("songs")
    if not isinstance(songs, list):
        _schema_error(issues, "songs")
    else:
        for index, song in enumerate(songs):
            if not isinstance(song, dict):
                _schema_error(issues, f"songs[{index}]")
                continue
            for field in ("id", "title", "audio", "lyrics_source"):
                if not _is_string(song.get(field)):
                    _schema_error(issues, f"songs[{index}].{field}")
            if not _is_int(song.get("order")):
                _schema_error(issues, f"songs[{index}].order")

    refined = manifest.get("refined")
    if not isinstance(refined, dict):
        _schema_error(issues, "refined")
    else:
        if not _is_string(refined.get("title")):
            _schema_error(issues, "refined.title")
        items = refined.get("items")
        if not isinstance(items, list):
            _schema_error(issues, "refined.items")
        else:
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    _schema_error(issues, f"refined.items[{index}]")
                    continue
                for field in ("type", "role", "title", "file"):
                    if not _is_string(item.get(field)):
                        _schema_error(issues, f"refined.items[{index}].{field}")
                if not _is_int(item.get("order")):
                    _schema_error(issues, f"refined.items[{index}].order")
                if "display" in item and not isinstance(item["display"], str):
                    _schema_error(issues, f"refined.items[{index}].display")

    sharing = manifest.get("sharing")
    if not isinstance(sharing, dict):
        _schema_error(issues, "sharing")
    elif any(key not in {"description", "image_alt"} or not isinstance(value, str) for key, value in sharing.items()):
        _schema_error(issues, "sharing")

    excluded = manifest.get("excluded_files")
    if not isinstance(excluded, list) or not all(_is_string(path) for path in excluded):
        _schema_error(issues, "excluded_files")


def _validate_duplicates(manifest: dict, issues: list[Issue]) -> None:
    raw_songs = manifest.get("songs")
    songs = [song for song in raw_songs if isinstance(song, dict)] if isinstance(raw_songs, list) else []
    ids = [song["id"] for song in songs if _is_string(song.get("id"))]
    if len(ids) != len(set(ids)):
        issues.append(_issue("duplicate_id", "詩歌 id 不得重複", "songs"))
    song_orders = [song["order"] for song in songs if _is_int(song.get("order"))]
    if len(song_orders) != len(set(song_orders)):
        issues.append(_issue("duplicate_order", "詩歌 order 不得重複", "songs"))

    refined = manifest.get("refined", {})
    raw_items = refined.get("items") if isinstance(refined, dict) else []
    items = raw_items if isinstance(raw_items, list) else []
    orders = [item["order"] for item in items if isinstance(item, dict) and _is_int(item.get("order"))]
    if len(orders) != len(set(orders)):
        issues.append(_issue("duplicate_order", "精煉項目 order 不得重複", "refined.items"))


def _valid_visual_field(visual: object, field: str) -> bool:
    if not isinstance(visual, dict):
        return False
    value = visual.get(field)
    if field in {"palette", "mood", "distinctive_elements", "avoid"}:
        return isinstance(value, list) and bool(value) and all(_is_string(item) for item in value)
    return _is_string(value)


def _validate_visual(manifest: dict, issues: list[Issue]) -> None:
    visual = manifest.get("visual")
    missing = [field for field in _VISUAL_FIELDS if not _valid_visual_field(visual, field)]
    if missing:
        issues.append(_issue("visual_brief_incomplete", f"視覺 DNA 不完整：{', '.join(missing)}", "visual"))


def _validate_source_mapping(manifest: dict, inventory: dict, issues: list[Issue]) -> None:
    files = inventory.get("files") if isinstance(inventory, dict) else []
    inventory_paths = {item["path"] for item in files if isinstance(item, dict) and isinstance(item.get("path"), str)}
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
    if not isinstance(inventory, dict) or manifest.get("inventory_digest") != inventory.get("inventory_digest"):
        issues.append(_issue("inventory_mismatch", "來源目錄指紋與 manifest 不一致", "inventory_digest"))
    if not isinstance(inventory, dict) or manifest.get("chapter") != inventory.get("chapter"):
        issues.append(_issue("inventory_mismatch", "章號與來源目錄不一致", "chapter"))
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
