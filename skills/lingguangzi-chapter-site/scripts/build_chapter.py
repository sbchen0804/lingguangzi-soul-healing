"""Build a confirmed chapter manifest into an isolated static chapter tree."""

from __future__ import annotations

from html import escape
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
from tempfile import mkdtemp
from urllib.parse import urljoin, urlparse

try:
    from chapter_types import read_json, write_json
    from extract_lyrics import extract_lyrics
    from manifest import validate_manifest
    from render_pdf_pages import render_pdf_pages
    from scan_chapter import scan_chapter
except ImportError:  # pragma: no cover - package invocation support
    from .chapter_types import read_json, write_json
    from .extract_lyrics import extract_lyrics
    from .manifest import validate_manifest
    from .render_pdf_pages import render_pdf_pages
    from .scan_chapter import scan_chapter


class BuildBlocked(RuntimeError):
    """Raised when chapter inputs cannot safely produce a static page."""


TEMPLATE_ROOT = Path(__file__).parents[1] / "assets" / "chapter-template"
_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")


def _text(value: object) -> str:
    return escape(str(value) if value is not None else "", quote=True)


def _safe_lyrics(value: object) -> str:
    """Keep only semantic lyrics tags emitted by extract_lyrics; escape all else."""
    raw = str(value or "")
    parts = re.split(r"(<(?:/p|p|br)>)", raw, flags=re.IGNORECASE)
    safe = []
    for part in parts:
        if re.fullmatch(r"<(?:/p|p|br)>", part, flags=re.IGNORECASE):
            safe.append(part.lower())
        else:
            safe.append(escape(part))
    return "".join(safe)


def _description(manifest: dict) -> str:
    sharing = manifest.get("sharing") if isinstance(manifest.get("sharing"), dict) else {}
    description = sharing.get("description")
    if isinstance(description, str) and description.strip():
        return description.strip()
    keywords = manifest.get("theme", {}).get("keywords", []) if isinstance(manifest.get("theme"), dict) else []
    suffix = "、".join(str(item) for item in keywords if str(item).strip())
    base = f"{manifest.get('title', '')}：{manifest.get('subtitle', '')}".strip("：")
    return f"{base}。{suffix}".strip("。")


def _absolute_url(base: str, relative: str) -> str:
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise BuildBlocked("public_url must be an absolute HTTPS URL without credentials")
    return urljoin(base.rstrip("/") + "/", relative)


def _safe_public_asset(value: object) -> str:
    """Accept only a chapter-local emitted asset path for share metadata."""
    if not isinstance(value, str) or not value or "\\" in value or _WINDOWS_DRIVE.match(value):
        raise BuildBlocked("share image must be a local emitted asset path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts) or not path.parts[0] == "assets":
        raise BuildBlocked("share image must be a local emitted asset path")
    return path.as_posix()


def render_head(manifest: dict, public_url: str) -> str:
    """Render escaped SEO, social, and Article metadata for a public chapter URL."""
    chapter = manifest.get("chapter", "")
    title = str(manifest.get("title", "")).strip()
    page_title = f"{title}｜靈魂療癒系列第 {chapter} 章"
    description = _description(manifest)
    visual = manifest.get("visual") if isinstance(manifest.get("visual"), dict) else {}
    share = _safe_public_asset(visual.get("share", "assets/share.png"))
    share_url = _absolute_url(public_url, share)
    sharing = manifest.get("sharing") if isinstance(manifest.get("sharing"), dict) else {}
    image_alt = str(sharing.get("image_alt") or title)
    article = {
        "@context": "https://schema.org", "@type": "Article", "headline": title,
        "description": description, "image": share_url, "mainEntityOfPage": public_url,
        "author": {"@type": "Person", "name": "柯萬盛醫師（筆名靈光子）"},
    }
    article_json = json.dumps(article, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return "\n".join((
        '<meta charset="utf-8">', '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{_text(page_title)}</title>", f'<meta name="description" content="{_text(description)}">',
        f'<link rel="canonical" href="{_text(public_url)}">', '<meta property="og:type" content="article">',
        '<meta property="og:locale" content="zh_TW">', '<meta property="og:site_name" content="靈魂療癒系列">',
        f'<meta property="og:title" content="{_text(page_title)}">', f'<meta property="og:description" content="{_text(description)}">',
        f'<meta property="og:url" content="{_text(public_url)}">', f'<meta property="og:image" content="{_text(share_url)}">',
        '<meta property="og:image:width" content="1200">', '<meta property="og:image:height" content="630">',
        f'<meta property="og:image:alt" content="{_text(image_alt)}">', '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{_text(page_title)}">', f'<meta name="twitter:description" content="{_text(description)}">',
        f'<meta name="twitter:image" content="{_text(share_url)}">', f'<script type="application/ld+json">{article_json}</script>',
    ))


def render_entry_nav(chapter: int) -> str:
    return (
        f'<nav class="entry-nav" id="entry-{chapter}" aria-label="本章閱讀方式">'
        '<p>選擇你的閱讀方式</p><div class="entry-list">'
        f'<a class="entry active" data-entry href="#original-{chapter}" aria-current="true"><b>原圖文</b><small>閱讀柯醫師原作</small></a>'
        f'<a class="entry" data-entry href="#song-{chapter}"><b>詩歌呈現</b><small>聆聽本章詩歌</small></a>'
        f'<a class="entry" data-entry href="#refined-{chapter}"><b>精煉篇</b><small>找回生命的處方</small></a>'
        '</div></nav>'
    )


def render_original(manifest: dict, assets: dict) -> str:
    chapter = manifest["chapter"]
    original = manifest.get("original", {})
    cover = _text(assets.get(original.get("cover"), ""))
    document = _text(assets.get(original.get("pdf"), ""))
    pages = assets.get(f"pages:{original.get('pdf')}", [])
    page_html = "".join(
        f'<figure><img loading="lazy" src="{_text(page)}" alt="原圖文第 {number} 頁"><figcaption>第 {number} 頁</figcaption></figure>'
        for number, page in enumerate(pages, 1)
    )
    return (
        f'<section class="original-intro" id="original-{chapter}"><div class="content two-col">'
        f'<img src="{cover}" alt="{_text(manifest.get("title"))}原圖文封面"><div><p class="eyebrow">ORIGINAL WORDS</p>'
        f'<h2>靈光子的原圖文</h2><p>{_text(manifest.get("subtitle"))}</p>'
        f'<a class="primary-button" href="#original-reader-{chapter}">線上閱讀原圖文</a>'
        f'<p class="reading-guidance">如需保存或列印，再<a href="{document}" download>下載 PDF 留存</a>。</p></div></div></section>'
        f'<section class="content original-reader" id="original-reader-{chapter}"><p class="eyebrow">ORIGINAL WORDS · ONLINE READING</p>'
        f'<h2>原圖文完整閱讀</h2><div class="page-stack" aria-label="原圖文完整閱讀">{page_html}</div></section>'
    )


def render_songs(songs: list[dict], assets: dict) -> str:
    cards = []
    for song in sorted((item for item in songs if isinstance(item, dict)), key=lambda item: item.get("order", 0)):
        audio = _text(assets.get(song.get("id"), assets.get(song.get("audio"), "")))
        cards.append(
            f'<article class="song-card"><p class="eyebrow">SONG {_text(song.get("order"))}</p><h3>{_text(song.get("title"))}</h3>'
            f'<audio controls preload="metadata" data-title="{_text(song.get("title"))}" src="{audio}">你的瀏覽器不支援音訊播放。</audio>'
            f'<details class="lyrics"><summary>閱讀歌詞</summary><div class="lyrics-copy" aria-label="{_text(song.get("title"))}歌詞">{_safe_lyrics(song.get("lyrics_html"))}</div></details></article>'
        )
    return '<section class="content song-section" id="song-{0}"><p class="eyebrow">MUSIC</p><h2>詩歌呈現</h2><div class="song-list">{1}</div></section>'.format(
        _text(songs[0].get("chapter", "")) if songs else "", "".join(cards))


def render_refined(items: list[dict], assets: dict) -> str:
    blocks = []
    for item in sorted((value for value in items if isinstance(value, dict)), key=lambda value: value.get("order", 0)):
        file_url = _text(assets.get(item.get("file"), ""))
        title = _text(item.get("title"))
        kind = item.get("type")
        if kind == "image":
            content = f'<img class="wisdom-image" src="{file_url}" alt="{title}">'
        elif kind == "document":
            pages = assets.get(f"pages:{item.get('file')}", [])
            content = '<div class="page-stack" aria-label="精煉篇全文">' + "".join(
                f'<figure><img loading="lazy" src="{_text(page)}" alt="{title}第 {number} 頁"><figcaption>第 {number} 頁</figcaption></figure>'
                for number, page in enumerate(pages, 1)) + '</div>'
        elif kind == "audio":
            content = f'<audio controls preload="metadata" data-title="{title}" src="{file_url}">你的瀏覽器不支援音訊播放。</audio>'
        elif kind == "video":
            content = f'<video controls preload="metadata" data-title="{title}" src="{file_url}">你的瀏覽器不支援影片播放。</video>'
        else:
            continue
        blocks.append(f'<article class="reading-block"><p class="eyebrow">{_text(item.get("order"))} · {_text(str(kind).upper())}</p><h3>{title}</h3>{content}</article>')
    return '<section class="content refined-section" id="refined-{0}"><p class="eyebrow">REFINED READING</p><h2>{1}</h2><div class="reading-sequence">{2}</div></section>'.format(
        _text(assets.get("chapter", "")), _text(assets.get("refined_title", "找回生命的靈魂處方")), "".join(blocks))


def render_footer(manifest: dict, analytics: dict) -> str:
    enabled = bool(analytics.get("goatcounter_code")) if isinstance(analytics, dict) else False
    counter = '本章瀏覽次數將於正式網站顯示。' if enabled else '本機預覽不計入瀏覽次數。'
    return f'<footer>原作作者：柯萬盛醫師（筆名靈光子）<br>本系列內容經作者同意公開分享<br>{_text(counter)} 統計僅用於了解閱讀情形。</footer>'


def _safe_source(root: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative or _WINDOWS_DRIVE.match(relative):
        raise BuildBlocked("unsafe source asset path")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        raise BuildBlocked("unsafe source asset path")
    candidate = root.joinpath(*pure.parts)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (FileNotFoundError, ValueError, OSError) as error:
        raise BuildBlocked(f"missing or unsafe source asset: {relative}") from error
    if not resolved.is_file():
        raise BuildBlocked(f"missing source asset: {relative}")
    return resolved


def _copy_asset(source_root: Path, stage: Path, relative: str) -> str:
    source = _safe_source(source_root, relative)
    target = stage / "assets" / Path(*PurePosixPath(relative).parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise BuildBlocked(f"asset output collision: {relative}")
    shutil.copyfile(source, target)
    return target.relative_to(stage).as_posix()


def _validate_inputs(manifest_path: Path) -> tuple[dict, Path]:
    manifest = read_json(manifest_path)
    if manifest.get("status") != "confirmed":
        raise BuildBlocked("confirmed manifest is required")
    source = manifest_path.parent.resolve()
    inventory = scan_chapter(source)
    lock_path = source / "chapter.lock.json"
    try:
        lock = read_json(lock_path)
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise BuildBlocked("matching chapter.lock.json is required") from error
    expected = [{key: item[key] for key in ("path", "size", "modified_time", "sha256")} for item in inventory["files"]]
    lock_files = lock.get("files")
    locked_core = [
        {key: item.get(key) for key in ("path", "size", "modified_time", "sha256")}
        for item in lock_files
    ] if isinstance(lock_files, list) and all(isinstance(item, dict) for item in lock_files) else None
    if lock.get("chapter") != inventory["chapter"] or lock.get("inventory_digest") != inventory["inventory_digest"] or locked_core != expected:
        raise BuildBlocked("chapter lock does not match current source inventory")
    issues = validate_manifest(manifest, inventory)
    if issues:
        raise BuildBlocked("manifest is invalid: " + ", ".join(issue.code for issue in issues))
    return manifest, source


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_manifest(output: Path, chapter: int) -> dict:
    files = []
    for path in sorted((entry for entry in output.rglob("*") if entry.is_file() and entry.name != "build.manifest.json"), key=lambda entry: entry.relative_to(output).as_posix()):
        files.append({"path": path.relative_to(output).as_posix(), "size": path.stat().st_size, "sha256": _sha256(path)})
    return {"chapter": chapter, "files": files, "self_included": False}


def build_chapter(manifest_path: Path, site_root: Path) -> dict:
    """Build a new `chapters/{chapter}` tree without mutating chapter sources."""
    manifest_path = Path(manifest_path).resolve()
    manifest, source_root = _validate_inputs(manifest_path)
    site_root = Path(site_root).resolve()
    try:
        site_root.relative_to(source_root)
        raise BuildBlocked("site output cannot be inside source directory")
    except ValueError:
        pass
    try:
        source_root.relative_to(site_root)
        raise BuildBlocked("site output cannot contain source directory")
    except ValueError:
        pass
    chapter = manifest["chapter"]
    output = site_root / "chapters" / str(chapter)
    if output.exists():
        raise BuildBlocked(f"refusing to overwrite existing chapter output: {output}")
    config_path = site_root / "site.config.json"
    config = read_json(config_path) if config_path.is_file() else {}
    public_base = config.get("public_url", "https://example.invalid/")
    public_url = _absolute_url(str(public_base), f"chapters/{chapter}/")

    site_root.mkdir(parents=True, exist_ok=True)
    staging_parent = Path(mkdtemp(prefix=f".chapter-{chapter}-", dir=site_root))
    stage = staging_parent / str(chapter)
    try:
        stage.mkdir()
        assets: dict = {"chapter": str(chapter), "refined_title": manifest.get("refined", {}).get("title", "")}
        original = manifest["original"]
        for relative in (original["cover"], original["pdf"]):
            assets[relative] = _copy_asset(source_root, stage, relative)
        for song in manifest["songs"]:
            assets[song["id"]] = _copy_asset(source_root, stage, song["audio"])
            lyrics = extract_lyrics(_safe_source(source_root, song["lyrics_source"]))
            song["lyrics_html"] = lyrics["html"]
        for item in manifest["refined"]["items"]:
            assets[item["file"]] = _copy_asset(source_root, stage, item["file"])
        hero_relative = manifest.get("visual", {}).get("hero", original["cover"])
        if hero_relative not in assets:
            assets[hero_relative] = _copy_asset(source_root, stage, hero_relative)
        share_relative = manifest.get("visual", {}).get("share")
        if share_relative:
            assets[share_relative] = _copy_asset(source_root, stage, share_relative)
            manifest["visual"]["share"] = assets[share_relative]
        else:
            manifest["visual"]["share"] = assets[hero_relative]
        original_pages = render_pdf_pages(_safe_source(source_root, original["pdf"]), stage / "assets" / "pages", f"original-{chapter}")
        assets[f"pages:{original['pdf']}"] = [Path(page["path"]).relative_to(stage).as_posix() for page in original_pages]
        for item in manifest["refined"]["items"]:
            if item["type"] == "document":
                pages = render_pdf_pages(_safe_source(source_root, item["file"]), stage / "assets" / "pages", f"refined-{chapter}-{item['order']}")
                assets[f"pages:{item['file']}"] = [Path(page["path"]).relative_to(stage).as_posix() for page in pages]
        template = (TEMPLATE_ROOT / "chapter.html").read_text(encoding="utf-8")
        tokens = {
            "head": render_head(manifest, public_url), "chapter": _text(chapter), "entry_href": "#entry-" + _text(chapter),
            "title": _text(manifest["title"]), "subtitle": _text(manifest["subtitle"]), "hero_url": _text(assets[hero_relative]),
            "hero_alt": _text(manifest.get("sharing", {}).get("image_alt") or manifest["title"]), "entry_nav": render_entry_nav(chapter),
            "original": render_original(manifest, assets), "songs": render_songs([{**song, "chapter": chapter} for song in manifest["songs"]], assets),
            "refined": render_refined(manifest["refined"]["items"], assets), "footer": render_footer(manifest, config.get("analytics", {})),
        }
        for key, value in tokens.items():
            template = template.replace("{{" + key + "}}", value)
        (stage / "index.html").write_text(template, encoding="utf-8")
        shutil.copyfile(TEMPLATE_ROOT / "styles.css", stage / "styles.css")
        shutil.copyfile(TEMPLATE_ROOT / "chapter.js", stage / "chapter.js")
        write_json(stage / "build.manifest.json", _build_manifest(stage, chapter))
        output.parent.mkdir(parents=True, exist_ok=True)
        stage.replace(output)
        return {"chapter": chapter, "output": str(output), "public_url": public_url, "build_manifest": str(output / "build.manifest.json")}
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise
    finally:
        if staging_parent.exists():
            shutil.rmtree(staging_parent)
