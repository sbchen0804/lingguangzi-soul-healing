from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

SCRIPTS = Path(__file__).parents[2] / "skills/lingguangzi-chapter-site/scripts"
sys.path.insert(0, str(SCRIPTS))

from chapter_types import Issue, read_json, write_json
from manifest import confirm_manifest, draft_manifest, invalidate_if_changed, validate_manifest
from scan_chapter import _chapter_number, inventory_digest, scan_chapter


class SharedTypeTests(unittest.TestCase):
    def test_issue_and_json_round_trip(self):
        with TemporaryDirectory() as raw:
            target = Path(raw) / "state.json"
            write_json(target, {"issues": [Issue("missing", "blocking", "缺少檔案", None).as_dict()]})
            self.assertEqual(read_json(target)["issues"][0]["severity"], "blocking")


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).parent / "fixtures/chapter-999"

    def test_scan_records_relative_paths_hashes_and_roles(self):
        result = scan_chapter(self.root)
        paths = {item["path"] for item in result["files"]}
        self.assertIn("原圖文/cover.png", paths)
        self.assertIn("詩歌創作/lyrics.txt", paths)
        self.assertTrue(all(len(item["sha256"]) == 64 for item in result["files"]))
        self.assertEqual(result["chapter"], 999)
        self.assertTrue(result["inventory_digest"].startswith("sha256:"))
        cover = next(item for item in result["files"] if item["path"] == "原圖文/cover.png")
        self.assertEqual(cover["role_candidates"], ["original.cover"])
        lyrics = next(item for item in result["files"] if item["path"] == "詩歌創作/lyrics.txt")
        self.assertEqual(lyrics["role_candidates"], ["song.lyrics_source"])

    def test_scan_is_stable_when_directory_is_unchanged(self):
        self.assertEqual(scan_chapter(self.root)["inventory_digest"], scan_chapter(self.root)["inventory_digest"])

    def test_cli_write_creates_inventory_and_lock_only(self):
        from tempfile import TemporaryDirectory
        import subprocess
        with TemporaryDirectory() as raw:
            root = Path(raw) / "靈魂療癒系列第 999 章"
            for source in self.root.rglob("*"):
                if source.is_file():
                    target = root / source.relative_to(self.root)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(source.read_bytes())
            script = SCRIPTS / "scan_chapter.py"
            completed = subprocess.run([sys.executable, str(script), str(root), "--write"], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((root / "chapter.inventory.json").exists())
            self.assertTrue((root / "chapter.lock.json").exists())
            self.assertFalse((root / "chapter.json").exists())
            lock = read_json(root / "chapter.lock.json")
            self.assertEqual(lock["inventory_digest"], read_json(root / "chapter.inventory.json")["inventory_digest"])

    def test_scan_normalizes_unicode_paths_and_sorts_by_normalized_path(self):
        with TemporaryDirectory() as raw:
            root = Path(raw) / "chapter-999"
            folder = root / "原圖文"
            folder.mkdir(parents=True)
            (folder / "z.png").write_bytes(b"z")
            (folder / "cafe\u0301.png").write_bytes(b"accent")
            paths = [item["path"] for item in scan_chapter(root)["files"]]
            self.assertEqual(paths, ["原圖文/café.png", "原圖文/z.png"])

    def test_inventory_digest_excludes_modified_time_and_unrelated_fields(self):
        files = [{"path": "a.txt", "size": 1, "sha256": "a" * 64, "modified_time": "one", "role_candidates": ["unknown"]}]
        changed = [{**files[0], "modified_time": "two", "unrelated": "ignored"}]
        self.assertEqual(inventory_digest(files), inventory_digest(changed))

    def test_inventory_digest_normalizes_paths_before_sorting(self):
        decomposed = [{"path": "cafe\u0301.txt", "size": 1, "sha256": "a" * 64}]
        composed = [{"path": "café.txt", "size": 1, "sha256": "a" * 64}]
        self.assertEqual(inventory_digest(decomposed), inventory_digest(composed))

    def test_scan_rejects_normalized_relative_path_collisions(self):
        with TemporaryDirectory() as raw:
            root = Path(raw) / "chapter-999"
            root.mkdir()
            (root / "café.txt").write_text("one", encoding="utf-8")
            (root / "cafe\u0301.txt").write_text("two", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "normalized path collision.*café.txt"):
                scan_chapter(root)

    def test_scan_excludes_unsupported_suffixes(self):
        with TemporaryDirectory() as raw:
            root = Path(raw) / "chapter-999"
            root.mkdir()
            (root / "notes.csv").write_text("ignore", encoding="utf-8")
            (root / "keep.txt").write_text("keep", encoding="utf-8")
            self.assertEqual([item["path"] for item in scan_chapter(root)["files"]], ["keep.txt"])

    def test_chapter_parser_prioritizes_marker_and_rejects_invalid_or_ambiguous_names(self):
        self.assertEqual(_chapter_number(Path("靈魂療癒2026系列第 520 章")), 520)
        self.assertEqual(_chapter_number(Path("chapter-521")), 521)
        with self.assertRaises(ValueError):
            _chapter_number(Path("靈魂療癒系列"))
        with self.assertRaises(ValueError):
            _chapter_number(Path("chapter-520 chapter-521"))


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.inventory = scan_chapter(Path(__file__).parent / "fixtures/chapter-999")

    def test_draft_supports_multiple_songs_and_refined_items(self):
        draft = draft_manifest(self.inventory)
        self.assertEqual(draft["status"], "draft")
        self.assertIsInstance(draft["songs"], list)
        self.assertIsInstance(draft["refined"]["items"], list)

    def test_confirm_requires_all_supported_files_mapped_or_excluded(self):
        issues = validate_manifest(draft_manifest(self.inventory), self.inventory)
        self.assertTrue(any(issue.code == "unmapped_file" for issue in issues))

    def test_source_change_invalidates_confirmation(self):
        manifest = {"status": "confirmed", "inventory_digest": "sha256:old", "revision": 1}
        changed = invalidate_if_changed(manifest, {"inventory_digest": "sha256:new"})
        self.assertEqual(changed["status"], "draft")
        self.assertEqual(changed["revision"], 2)

    def test_wrong_chapter_is_an_inventory_mismatch(self):
        manifest = self._complete_manifest()
        manifest["chapter"] = 998
        self.assertIn("inventory_mismatch", self._codes(manifest))

    def test_missing_required_field_has_stable_code(self):
        manifest = self._complete_manifest()
        manifest["title"] = ""
        self.assertIn("missing_required_field", self._codes(manifest))

    def test_missing_source_file_has_stable_code(self):
        manifest = self._complete_manifest()
        manifest["original"]["cover"] = "原圖文/missing.png"
        self.assertIn("missing_source_file", self._codes(manifest))

    def test_duplicate_song_id_has_stable_code(self):
        manifest = self._complete_manifest()
        manifest["songs"].append({**manifest["songs"][0], "order": 2})
        self.assertIn("duplicate_id", self._codes(manifest))

    def test_duplicate_song_order_has_stable_code(self):
        manifest = self._complete_manifest()
        manifest["songs"].append({**manifest["songs"][0], "id": "song-02"})
        self.assertIn("duplicate_order", self._codes(manifest))

    def test_unmapped_file_has_stable_code(self):
        manifest = self._complete_manifest()
        manifest["original"].pop("cover")
        self.assertIn("unmapped_file", self._codes(manifest))

    def test_digest_mismatch_has_stable_code(self):
        manifest = self._complete_manifest()
        manifest["inventory_digest"] = "sha256:stale"
        self.assertIn("inventory_mismatch", self._codes(manifest))

    def test_incomplete_visual_brief_has_stable_code(self):
        manifest = self._complete_manifest()
        manifest["visual"] = {"style_family": "watercolor"}
        self.assertIn("visual_brief_incomplete", self._codes(manifest))

    def test_malformed_containers_are_blocking_issues_not_crashes(self):
        manifest = self._complete_manifest()
        manifest.update({"songs": None, "refined": [], "sharing": [], "excluded_files": {"cover"}})
        issues = validate_manifest(manifest, self.inventory)
        self.assertTrue(issues)
        self.assertTrue(all(issue.severity == "blocking" for issue in issues))
        self.assertIn("missing_required_field", {issue.code for issue in issues})

    def test_invalid_schema_types_and_visual_lists_are_blocking(self):
        manifest = self._complete_manifest()
        manifest.update({"schema_version": "1", "revision": "0", "status": "ready", "chapter": True})
        manifest["theme"] = {"keywords": "health", "visual_notes": []}
        manifest["visual"]["palette"] = "blue"
        manifest["visual"]["mood"] = "calm"
        manifest["visual"]["distinctive_elements"] = "door"
        manifest["visual"]["avoid"] = "lake"
        manifest["songs"][0]["order"] = "1"
        issues = validate_manifest(manifest, self.inventory)
        self.assertTrue(issues)
        self.assertIn("missing_required_field", {issue.code for issue in issues})
        self.assertIn("visual_brief_incomplete", {issue.code for issue in issues})

    def test_unhashable_song_and_refined_values_are_blocking_issues_not_crashes(self):
        manifest = self._complete_manifest()
        manifest["songs"][0]["id"] = []
        manifest["songs"][0]["order"] = {}
        manifest["refined"] = {"title": "精煉篇", "items": [{
            "type": "image", "role": "card", "title": "圖卡", "file": "原圖文/cover.png", "order": [],
        }]}
        manifest["sharing"] = {"description": []}
        issues = validate_manifest(manifest, self.inventory)
        self.assertTrue(issues)
        self.assertTrue(all(issue.severity == "blocking" for issue in issues))
        self.assertIn("missing_required_field", {issue.code for issue in issues})

    def test_excluding_all_supported_files_is_a_valid_mapping(self):
        manifest = self._complete_manifest()
        manifest["original"] = {"cover": "原圖文/cover.png", "pdf": "原圖文/original.pdf"}
        manifest["songs"] = []
        manifest["excluded_files"] = ["詩歌創作/song.mp3", "詩歌創作/lyrics.txt"]
        self.assertEqual(validate_manifest(manifest, self.inventory), [])

    def test_mapped_and_excluded_file_is_not_a_valid_mapping(self):
        manifest = self._complete_manifest()
        manifest["excluded_files"] = ["詩歌創作/song.mp3"]
        self.assertIn("unmapped_file", self._codes(manifest))

    def test_refined_duplicate_order_has_stable_code(self):
        manifest = self._complete_manifest()
        manifest["songs"] = []
        manifest["excluded_files"] = ["詩歌創作/song.mp3", "詩歌創作/lyrics.txt"]
        manifest["refined"]["items"] = [
            {"type": "image", "role": "card", "title": "封面", "file": "原圖文/cover.png", "order": 1},
            {"type": "document", "role": "source", "title": "原作", "file": "原圖文/original.pdf", "order": 1},
        ]
        manifest["original"] = {}
        self.assertIn("duplicate_order", self._codes(manifest))

    def test_confirm_writes_a_current_confirmed_revision_after_mapping_all_files(self):
        manifest = self._complete_manifest()
        with TemporaryDirectory() as raw:
            path = Path(raw) / "chapter.json"
            write_json(path, manifest)
            confirmed = confirm_manifest(path, self.inventory)
            self.assertEqual(confirmed["status"], "confirmed")
            self.assertEqual(confirmed["revision"], 1)
            self.assertEqual(confirmed["inventory_digest"], self.inventory["inventory_digest"])
            self.assertEqual(read_json(path), confirmed)
            self.assertEqual(list(Path(raw).glob("*.tmp")), [])

    def test_confirm_refuses_to_replace_manifest_when_blocking_issues_exist(self):
        manifest = draft_manifest(self.inventory)
        with TemporaryDirectory() as raw:
            path = Path(raw) / "chapter.json"
            write_json(path, manifest)
            before = path.read_text(encoding="utf-8")
            with self.assertRaises(ValueError):
                confirm_manifest(path, self.inventory)
            self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_confirm_refuses_wrong_chapter_and_malformed_data_without_confirming(self):
        manifests = []
        wrong_chapter = self._complete_manifest()
        wrong_chapter["chapter"] = 998
        manifests.append(wrong_chapter)
        malformed = self._complete_manifest()
        malformed["songs"] = None
        manifests.append(malformed)
        with TemporaryDirectory() as raw:
            for index, manifest in enumerate(manifests):
                path = Path(raw) / f"chapter-{index}.json"
                write_json(path, manifest)
                with self.assertRaises(ValueError):
                    confirm_manifest(path, self.inventory)
                self.assertNotEqual(read_json(path).get("status"), "confirmed")

    @staticmethod
    def _complete_visual():
        return {
            "style_family": "watercolor",
            "concept": "測試意象",
            "composition": "測試構圖",
            "palette": ["藍", "綠"],
            "mood": ["安穩"],
            "distinctive_elements": ["門"],
            "avoid": ["湖面"],
        }

    def _complete_manifest(self):
        manifest = draft_manifest(self.inventory)
        manifest.update({
            "title": "測試章節",
            "subtitle": "副標題",
            "original": {"cover": "原圖文/cover.png", "pdf": "原圖文/original.pdf"},
            "songs": [{
                "id": "song-01",
                "title": "測試詩歌",
                "audio": "詩歌創作/song.mp3",
                "lyrics_source": "詩歌創作/lyrics.txt",
                "order": 1,
            }],
            "visual": self._complete_visual(),
        })
        return manifest

    def _codes(self, manifest):
        return {issue.code for issue in validate_manifest(manifest, self.inventory)}
