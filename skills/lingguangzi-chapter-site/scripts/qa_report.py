"""Create one consolidated pre-publication QA report for a chapter build."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from chapter_types import Issue, read_json
    from visuals import validate_visual_brief
except ImportError:  # pragma: no cover
    from .chapter_types import Issue, read_json
    from .visuals import validate_visual_brief


CHECK_NAMES = (
    "manifest", "source_lock", "content", "pdf_pages", "media", "responsive",
    "navigation", "visual_distinctiveness", "meta", "counter", "publication_authorization",
)


def _check(status: str = "pass", issues: list[Issue] | None = None, evidence: list[str] | None = None) -> dict:
    return {"status": status, "issues": [issue.as_dict() for issue in issues or []], "evidence": evidence or []}


def _blocking(code: str, message: str, path: str | None = None) -> Issue:
    return Issue(code, "blocking", message, path)


def _warning(code: str, message: str, path: str | None = None) -> Issue:
    return Issue(code, "warning", message, path)


def collect_qa(manifest: dict, build_root: Path, visual_registry: list[dict]) -> dict:
    build_root = Path(build_root)
    checks = {name: _check() for name in CHECK_NAMES}
    if manifest.get("status") != "confirmed":
        issue = _blocking("manifest_unconfirmed", "chapter.json 尚未确认")
        checks["manifest"] = _check("blocked", [issue])
    else:
        checks["manifest"]["evidence"].append(f"revision={manifest.get('revision')}")

    lock = build_root / "build.manifest.json"
    if not lock.is_file():
        checks["source_lock"] = _check("blocked", [_blocking("build_manifest_missing", "缺少 build.manifest.json")])
    else:
        checks["source_lock"]["evidence"].append(str(lock))

    index = build_root / "index.html"
    html = index.read_text(encoding="utf-8") if index.is_file() else ""
    if not html:
        checks["content"] = _check("blocked", [_blocking("content_missing", "缺少章節 index.html")])
    else:
        checks["content"]["evidence"].append("index.html")

    page_images = list((build_root / "assets" / "pages").glob("*.png")) if (build_root / "assets" / "pages").is_dir() else []
    if not page_images:
        checks["pdf_pages"] = _check("blocked", [_blocking("pdf_pages_missing", "PDF 尚未转换为在线阅读页面")])
    else:
        checks["pdf_pages"]["evidence"].append(f"pages={len(page_images)}")

    expected_media = sum(1 for song in manifest.get("songs", []) if isinstance(song, dict)) + sum(
        1 for item in manifest.get("refined", {}).get("items", [])
        if isinstance(item, dict) and item.get("type") in {"audio", "video"}
    )
    actual_media = html.count("<audio ") + html.count("<video ")
    if expected_media != actual_media:
        checks["media"] = _check("blocked", [_blocking("media_mismatch", "页面媒体数量与清单不一致")], [f"expected={expected_media}", f"actual={actual_media}"])
    else:
        checks["media"]["evidence"].append(f"media={actual_media}")

    responsive_path = build_root / "responsive-evidence.json"
    if not responsive_path.is_file():
        checks["responsive"] = _check("blocked", [_blocking("responsive_pending", "手机与电脑响应式检查尚未完成")])
    else:
        evidence = read_json(responsive_path)
        if not evidence.get("passed"):
            checks["responsive"] = _check("blocked", [_blocking("responsive_failed", "响应式证据未通过")])
        else:
            checks["responsive"]["evidence"].append(str(responsive_path))

    navigation_tokens = ("class=\"entry-nav\"", "class=\"go-top\"", "chapter.js")
    if not all(token in html for token in navigation_tokens):
        checks["navigation"] = _check("blocked", [_blocking("navigation_missing", "三选项或 Go Top 导览缺失")])

    visual_issues = validate_visual_brief(manifest.get("visual", {}), visual_registry)
    if visual_issues:
        checks["visual_distinctiveness"] = _check("blocked", visual_issues)
    else:
        checks["visual_distinctiveness"]["evidence"].append("recent-six comparison passed")

    meta_tokens = ('rel="canonical"', 'property="og:image"', 'name="twitter:image"', 'application/ld+json')
    if not all(token in html for token in meta_tokens):
        checks["meta"] = _check("blocked", [_blocking("meta_missing", "Meta 或分享图语法不完整")])

    if "data-goatcounter" not in html:
        checks["counter"] = _check("warning", [_warning("counter_pending", "尚未设定 GoatCounter；不阻挡本机预览")])
    else:
        checks["counter"]["evidence"].append("GoatCounter configured")

    authorization = manifest.get("publication_authorization", {})
    if not isinstance(authorization, dict) or authorization.get("approved") is not True:
        checks["publication_authorization"] = _check("blocked", [_blocking("publication_not_authorized", "缺少作者公开分享授权记录")])
    else:
        checks["publication_authorization"]["evidence"].append(str(authorization.get("note", "approved")))

    issues = [issue for check in checks.values() for issue in check["issues"]]
    blocking = sum(1 for issue in issues if issue["severity"] == "blocking")
    warnings = sum(1 for issue in issues if issue["severity"] == "warning")
    return {
        "chapter": manifest.get("chapter"), "status": "blocked" if blocking else "ready",
        "blocking_count": blocking, "warning_count": warnings, "checks": checks, "issues": issues,
    }


def write_report(result: dict, output: Path) -> None:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# 第 {result.get('chapter')} 章集中 QA", "", f"状态：**{result.get('status')}**", ""]
    for name, check in result.get("checks", {}).items():
        lines.extend((f"## {name}", "", f"- 状态：{check.get('status')}",))
        lines.extend(f"- {item['severity']} · `{item['code']}`：{item['message']}" for item in check.get("issues", []))
        lines.extend(f"- 证据：{item}" for item in check.get("evidence", []))
        lines.append("")
    output.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("build_root", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--output", type=Path, default=Path("qa-report.md"))
    args = parser.parse_args(argv)
    registry = read_json(args.registry) if args.registry and args.registry.exists() else []
    result = collect_qa(read_json(args.manifest), args.build_root, registry)
    write_report(result, args.output)
    return 2 if result["blocking_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
