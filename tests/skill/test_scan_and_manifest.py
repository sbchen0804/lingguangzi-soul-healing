from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

SCRIPTS = Path(__file__).parents[2] / "skills/lingguangzi-chapter-site/scripts"
sys.path.insert(0, str(SCRIPTS))

from chapter_types import Issue, read_json, write_json
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
