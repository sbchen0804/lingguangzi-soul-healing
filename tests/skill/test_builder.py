from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
from unittest.mock import patch

from PIL import Image
from reportlab.pdfgen.canvas import Canvas


SCRIPTS = Path(__file__).parents[2] / "skills/lingguangzi-chapter-site/scripts"
sys.path.insert(0, str(SCRIPTS))

from build_chapter import (  # noqa: E402
    BuildBlocked,
    build_chapter,
    render_entry_nav,
    render_head,
    render_refined,
    render_songs,
)
from scan_chapter import scan_chapter  # noqa: E402


class BuilderTests(unittest.TestCase):
    """Behavior tests for the public static-chapter builder boundary."""

    def test_draft_manifest_cannot_build(self):
        with TemporaryDirectory() as raw:
            root = Path(raw)
            manifest = root / "chapter.json"
            manifest.write_text('{"status":"draft"}', encoding="utf-8")
            with self.assertRaises(BuildBlocked):
                build_chapter(manifest, root / "site")

    def test_build_rejects_a_lock_that_does_not_match_current_source(self):
        with TemporaryDirectory() as raw:
            source, manifest_path = self._confirmed_source(Path(raw))
            lock = json.loads((source / "chapter.lock.json").read_text(encoding="utf-8"))
            lock["inventory_digest"] = "sha256:stale"
            (source / "chapter.lock.json").write_text(json.dumps(lock), encoding="utf-8")

            with self.assertRaisesRegex(BuildBlocked, "lock"):
                build_chapter(manifest_path, Path(raw) / "site")

    def test_builder_accepts_machine_lock_records_with_role_metadata(self):
        with TemporaryDirectory() as raw:
            source, manifest_path = self._confirmed_source(Path(raw))
            lock = json.loads((source / "chapter.lock.json").read_text(encoding="utf-8"))
            for item in lock["files"]:
                item["role"] = "unknown"
            (source / "chapter.lock.json").write_text(json.dumps(lock), encoding="utf-8")

            result = build_chapter(manifest_path, self._site(Path(raw)))
            self.assertTrue(Path(result["output"]).is_dir())

    def test_build_rejects_missing_and_traversing_assets_without_writing_site(self):
        with TemporaryDirectory() as raw:
            source, manifest_path = self._confirmed_source(Path(raw))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["original"]["cover"] = "../outside.png"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            site = Path(raw) / "site"

            with self.assertRaisesRegex(BuildBlocked, "unsafe|missing"):
                build_chapter(manifest_path, site)
            self.assertFalse(site.exists())

    def test_build_rejects_a_symlinked_asset_that_escapes_chapter_source(self):
        with TemporaryDirectory() as raw:
            source, manifest_path = self._confirmed_source(Path(raw))
            outside = Path(raw) / "outside.png"
            outside.write_bytes(b"outside")
            cover = source / "原圖文/cover.png"
            cover.unlink()
            try:
                os.symlink(outside, cover)
            except OSError as error:
                self.skipTest(f"symlinks unavailable in this environment: {error}")
            inventory = scan_chapter(source)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["inventory_digest"] = inventory["inventory_digest"]
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            lock = {"chapter": inventory["chapter"], "inventory_digest": inventory["inventory_digest"], "files": [
                {key: item[key] for key in ("path", "size", "modified_time", "sha256")} for item in inventory["files"]
            ]}
            (source / "chapter.lock.json").write_text(json.dumps(lock), encoding="utf-8")

            with self.assertRaisesRegex(BuildBlocked, "unsafe"):
                build_chapter(manifest_path, Path(raw) / "site")

    def test_builder_copies_cover_bytes_and_lists_every_emitted_file_hash(self):
        with TemporaryDirectory() as raw:
            source, manifest_path = self._confirmed_source(Path(raw))
            site = self._site(Path(raw))
            result = build_chapter(manifest_path, site)
            output = Path(result["output"])
            copied_cover = output / "assets/原圖文/cover.png"
            source_cover = source / "原圖文/cover.png"
            self.assertEqual(copied_cover.read_bytes(), source_cover.read_bytes())

            build_manifest = json.loads((output / "build.manifest.json").read_text(encoding="utf-8"))
            paths = [item["path"] for item in build_manifest["files"]]
            self.assertNotIn("build.manifest.json", paths)
            self.assertEqual(paths, sorted(paths))
            self.assertEqual(set(paths), {
                path.relative_to(output).as_posix()
                for path in output.rglob("*")
                if path.is_file() and path.name != "build.manifest.json"
            })
            for item in build_manifest["files"]:
                payload = (output / item["path"]).read_bytes()
                self.assertEqual(item["sha256"], hashlib.sha256(payload).hexdigest())

    def test_builder_emits_ordered_multiple_songs_and_refined_native_media(self):
        with TemporaryDirectory() as raw:
            source, manifest_path = self._confirmed_source(Path(raw), multiple=True)
            result = build_chapter(manifest_path, self._site(Path(raw)))
            html = (Path(result["output"]) / "index.html").read_text(encoding="utf-8")
            self.assertEqual(html.count('class="song-card"'), 2)
            self.assertLess(html.index("第一首"), html.index("第二首"))
            self.assertLess(html.index("圖卡"), html.index("精煉全文"))
            self.assertLess(html.index("精煉全文"), html.index("聲音"))
            self.assertLess(html.index("聲音"), html.index("影片"))
            self.assertIn('<audio controls preload="metadata"', html)
            self.assertIn('<video controls preload="metadata"', html)
            self.assertIn("線上閱讀", html)

    def test_renderers_escape_untrusted_text_and_attribute_values(self):
        manifest = {
            "chapter": 999,
            "title": '章節 <script>alert(1)</script>',
            "subtitle": '副標題 & "quote"',
            "theme": {"keywords": ["平安", "<危險>"], "visual_notes": ""},
            "sharing": {"description": '說明 <img src=x>', "image_alt": '圖 " alt'},
            "original": {"cover": "cover.png", "pdf": "book.pdf"},
            "refined": {"title": "精煉"},
        }
        head = render_head(manifest, "https://example.test/chapters/999/")
        original = __import__("build_chapter").render_original(manifest, {"cover.png": "assets/cover.png", "book.pdf": "assets/book.pdf"})
        songs = render_songs([
            {"id": 'song" onclick="bad', "title": '歌 < 一 "引號"', "order": 1, "lyrics_html": "<p>安全歌詞</p>"},
        ], {'song" onclick="bad': "assets/song.mp3"})
        refined = render_refined([
            {"type": "image", "title": "圖 < 卡", "file": "image.png", "order": 1},
        ], {"image.png": "assets/image.png"})
        joined = head + original + songs + refined
        self.assertNotIn("<script>", joined)
        self.assertNotIn("<img src=x>", joined)
        self.assertIn("&lt;script&gt;", joined)
        self.assertIn("歌 &lt; 一 &quot;引號&quot;", joined)
        self.assertIn("圖 &lt; 卡", joined)

    def test_head_contains_accurate_canonical_open_graph_twitter_and_json_ld(self):
        manifest = {
            "chapter": 999,
            "title": "測試標題",
            "subtitle": "測試副標題",
            "theme": {"keywords": ["健康", "平安"]},
            "sharing": {"description": "自訂摘要", "image_alt": "分享圖"},
            "visual": {"share": "assets/share.png"},
        }
        head = render_head(manifest, "https://example.test/chapters/999/")
        for expected in (
            '<title>測試標題｜靈魂療癒系列第 999 章</title>',
            'name="description" content="自訂摘要"',
            'rel="canonical" href="https://example.test/chapters/999/"',
            'property="og:url" content="https://example.test/chapters/999/"',
            'property="og:image" content="https://example.test/chapters/999/assets/share.png"',
            'name="twitter:card" content="summary_large_image"',
            'application/ld+json',
        ):
            self.assertIn(expected, head)

    def test_build_requires_https_base_url_and_emits_it_in_all_public_metadata(self):
        with TemporaryDirectory() as raw:
            _, manifest_path = self._confirmed_source(Path(raw))
            site = self._site(Path(raw), "https://chapters.example/series")
            result = build_chapter(manifest_path, site)
            html = (Path(result["output"]) / "index.html").read_text(encoding="utf-8")
            url = "https://chapters.example/series/chapters/999/"
            self.assertEqual(result["public_url"], url)
            self.assertIn(f'rel="canonical" href="{url}"', html)
            self.assertIn(f'property="og:url" content="{url}"', html)
            self.assertIn(f'name="twitter:image" content="{url}assets/精煉篇_找回生命的靈魂處方/share.png"', html)
            self.assertIn(f'"mainEntityOfPage":"{url}"', html)

    def test_build_blocks_missing_or_non_https_base_url(self):
        with TemporaryDirectory() as raw:
            _, manifest_path = self._confirmed_source(Path(raw))
            for number, config in enumerate(({}, {"base_url": ""}, {"base_url": "http://example.test"}, {"base_url": []})):
                with self.subTest(config=config):
                    site = Path(raw) / f"site-{number}"
                    site.mkdir()
                    (site / "site.config.json").write_text(json.dumps(config), encoding="utf-8")
                    with self.assertRaises(BuildBlocked):
                        build_chapter(manifest_path, site)

    def test_builder_blocks_ocr_required_lyrics_instead_of_emitting_empty_lyrics(self):
        with TemporaryDirectory() as raw:
            _, manifest_path = self._confirmed_source(Path(raw))
            with patch("build_chapter.extract_lyrics", return_value={"status": "requires_ocr", "html": "", "warnings": ["OCR review"]}):
                with self.assertRaisesRegex(BuildBlocked, "lyrics.*OCR|OCR.*lyrics"):
                    build_chapter(manifest_path, self._site(Path(raw)))

    def test_render_songs_preserves_generated_escaped_lyrics_once_and_blocks_markup_injection(self):
        generated = '<p>風 &lt; 心 &amp; 今天<br>安穩</p>'
        html = render_songs([{"id": "song-01", "title": "歌", "order": 1, "lyrics_html": generated}], {"song-01": "assets/song.mp3", "chapter": 999})
        self.assertIn(generated, html)
        self.assertNotIn("&amp;lt;", html)
        hostile = render_songs([{"id": "song-01", "title": "歌", "order": 1, "lyrics_html": '<p onclick="bad">x</p><script>alert(1)</script>'}], {"song-01": "assets/song.mp3", "chapter": 999})
        self.assertNotIn('onclick="bad"', hostile)
        self.assertNotIn("<script>", hostile)

    def test_builder_blocks_missing_or_wrong_dimension_share_image(self):
        with TemporaryDirectory() as raw:
            source, manifest_path = self._confirmed_source(Path(raw))
            Image.new("RGB", (100, 100), "white").save(source / "精煉篇_找回生命的靈魂處方/share.png")
            self._refresh_manifest_lock(source, manifest_path)
            with self.assertRaisesRegex(BuildBlocked, "share.*1200x630"):
                build_chapter(manifest_path, self._site(Path(raw)))

    def test_builder_refuses_existing_reparse_point_in_output_path(self):
        with TemporaryDirectory() as raw:
            _, manifest_path = self._confirmed_source(Path(raw))
            site = self._site(Path(raw))
            (site / "chapters").mkdir()
            with patch("build_chapter._is_reparse_point", side_effect=lambda path: Path(path).name == "chapters"):
                with self.assertRaisesRegex(BuildBlocked, "reparse"):
                    build_chapter(manifest_path, site)

    def test_head_rejects_an_external_or_traversing_share_image_value(self):
        manifest = {"chapter": 999, "title": "標題", "subtitle": "副標題", "theme": {"keywords": []}, "sharing": {}}
        for share in ("https://tracker.example/share.png", "../share.png", "/share.png"):
            with self.subTest(share=share):
                manifest["visual"] = {"share": share}
                with self.assertRaises(BuildBlocked):
                    render_head(manifest, "https://example.test/chapters/999/")

    def test_template_has_required_navigation_and_mobile_media_semantics(self):
        root = Path(__file__).parents[2] / "skills/lingguangzi-chapter-site/assets/chapter-template"
        css = (root / "styles.css").read_text(encoding="utf-8")
        script = (root / "chapter.js").read_text(encoding="utf-8")
        for minimum in (
            "font-size:1.3rem", "clamp(1.55rem,7vw,2.05rem)", "font-size:1.05rem",
            "font-size:1rem", "font-size:1.06rem", "font-size:.8rem", "font-size:1.04rem",
            "font-size:1.02rem",
        ):
            self.assertIn(minimum, css)
        for semantic in (
            "const entryHash = `#entry-${document.body.dataset.chapter}`", "history.replaceState(null, \"\", location.pathname + location.search)",
            "scrollTo({ top: 0, behavior: \"auto\" })", "scrollIntoView({ behavior: \"smooth\", block: \"start\" })",
            "history.pushState(null, \"\", hash)", "addEventListener(\"pagehide\"", "item.currentTime = 0",
        ):
            self.assertIn(semantic, script)

    def test_entry_navigation_stays_specific_to_its_chapter(self):
        markup = render_entry_nav(42)
        self.assertIn('id="entry-42"', markup)
        self.assertIn('href="#original-42"', markup)
        self.assertIn('href="#song-42"', markup)
        self.assertIn('href="#refined-42"', markup)

    @staticmethod
    def _confirmed_source(root: Path, multiple: bool = False) -> tuple[Path, Path]:
        source = root / "chapter-999"
        original = source / "原圖文"
        songs = source / "詩歌創作"
        refined = source / "精煉篇_找回生命的靈魂處方"
        for folder in (original, songs, refined):
            folder.mkdir(parents=True)
        Image.new("RGB", (160, 220), "#dbe8df").save(original / "cover.png")
        Image.new("RGB", (1200, 630), "#cde8df").save(refined / "share.png")
        Image.new("RGB", (1600, 900), "#b9d8ca").save(refined / "hero.png")
        canvas = Canvas(str(original / "original.pdf"))
        canvas.drawString(72, 720, "chapter original")
        canvas.save()
        songs.joinpath("song-01.mp3").write_bytes(b"ID3 song one")
        songs.joinpath("song-01.txt").write_text("第一首歌詞", encoding="utf-8")
        if multiple:
            songs.joinpath("song-02.mp3").write_bytes(b"ID3 song two")
            songs.joinpath("song-02.txt").write_text("第二首歌詞", encoding="utf-8")
            Image.new("RGB", (160, 120), "#cde8df").save(refined / "image.png")
            canvas = Canvas(str(refined / "refined.pdf"))
            canvas.drawString(72, 720, "refined page")
            canvas.save()
            refined.joinpath("audio.m4a").write_bytes(b"audio")
            refined.joinpath("video.mp4").write_bytes(b"video")

        inventory = scan_chapter(source)
        lock = {
            "chapter": inventory["chapter"], "inventory_digest": inventory["inventory_digest"],
            "files": [{key: item[key] for key in ("path", "size", "modified_time", "sha256")} for item in inventory["files"]],
        }
        (source / "chapter.lock.json").write_text(json.dumps(lock, ensure_ascii=False), encoding="utf-8")
        manifest = {
            "schema_version": 1, "revision": 1, "status": "confirmed",
            "inventory_digest": inventory["inventory_digest"], "chapter": 999,
            "title": "測試章節", "subtitle": "把今天活好",
            "theme": {"keywords": ["健康", "今天"], "visual_notes": ""},
            "visual": {
                "style_family": "watercolor", "concept": "今天", "composition": "留白",
                "palette": ["綠"], "mood": ["安穩"], "distinctive_elements": ["光"], "avoid": ["湖"],
                "hero": "精煉篇_找回生命的靈魂處方/hero.png", "share": "精煉篇_找回生命的靈魂處方/share.png",
            },
            "original": {"cover": "原圖文/cover.png", "pdf": "原圖文/original.pdf"},
            "songs": [{"id": "song-01", "title": "第一首", "audio": "詩歌創作/song-01.mp3", "lyrics_source": "詩歌創作/song-01.txt", "order": 1}],
            "refined": {"title": "找回生命的靈魂處方", "items": []},
            "sharing": {"published_at": "2026-09-01", "modified_at": "2026-09-01"}, "excluded_files": [],
        }
        if multiple:
            manifest["songs"].append({"id": "song-02", "title": "第二首", "audio": "詩歌創作/song-02.mp3", "lyrics_source": "詩歌創作/song-02.txt", "order": 2})
            manifest["refined"]["items"] = [
                {"type": "image", "role": "card", "title": "圖卡", "file": "精煉篇_找回生命的靈魂處方/image.png", "order": 1},
                {"type": "document", "role": "full-text", "title": "精煉全文", "file": "精煉篇_找回生命的靈魂處方/refined.pdf", "display": "online-pages", "order": 2},
                {"type": "audio", "role": "podcast", "title": "聲音", "file": "精煉篇_找回生命的靈魂處方/audio.m4a", "order": 3},
                {"type": "video", "role": "feature", "title": "影片", "file": "精煉篇_找回生命的靈魂處方/video.mp4", "order": 4},
            ]
        manifest_path = source / "chapter.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        return source, manifest_path

    @staticmethod
    def _site(root: Path, base_url: str = "https://example.test/") -> Path:
        site = root / "site"
        site.mkdir(exist_ok=True)
        (site / "site.config.json").write_text(json.dumps({"base_url": base_url}), encoding="utf-8")
        return site

    @staticmethod
    def _refresh_manifest_lock(source: Path, manifest_path: Path) -> None:
        inventory = scan_chapter(source)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["inventory_digest"] = inventory["inventory_digest"]
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        (source / "chapter.lock.json").write_text(json.dumps({"chapter": inventory["chapter"], "inventory_digest": inventory["inventory_digest"], "files": [{key: item[key] for key in ("path", "size", "modified_time", "sha256")} for item in inventory["files"]]}), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
