from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

SCRIPTS = Path(__file__).parents[2] / "skills/lingguangzi-chapter-site/scripts"
sys.path.insert(0, str(SCRIPTS))

from qa_report import CHECK_NAMES, collect_qa, write_report  # noqa: E402
from visuals import recent_visuals, register_visual, validate_visual_brief, visual_differences  # noqa: E402


class VisualTests(unittest.TestCase):
    def test_requires_three_differences_and_blocks_recent_repeat(self):
        previous = {"chapter": 521, "concept": "死亡与今天", "composition": "湖面远景", "palette": ["金", "绿"], "distinctive_elements": ["湖", "山"], "lighting": "日出"}
        current = {"concept": "风穿心门", "composition": "室内向外", "palette": ["蓝", "琥珀"], "distinctive_elements": ["门", "纱帘"], "lighting": "午後"}
        self.assertGreaterEqual(len(visual_differences(current, previous)), 3)
        self.assertEqual(validate_visual_brief(current, [previous]), [])
        self.assertTrue(validate_visual_brief(previous, [previous]))

    def test_registry_is_sorted_replaced_and_recent_six(self):
        with TemporaryDirectory() as raw:
            path = Path(raw) / "registry.json"
            for chapter in (520, 521, 519, 520):
                register_visual(path, {"chapter": chapter, "concept": str(chapter)})
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual([item["chapter"] for item in payload], [519, 520, 521])
            self.assertEqual([item["chapter"] for item in recent_visuals(payload, 2)], [520, 521])


class QaTests(unittest.TestCase):
    def test_report_has_all_named_checks_and_blocks_missing_evidence(self):
        manifest = {"status": "confirmed", "chapter": 520, "revision": 1, "songs": [], "refined": {"items": []}, "visual": {}, "publication_authorization": {"approved": True}}
        with TemporaryDirectory() as raw:
            result = collect_qa(manifest, Path(raw), [])
            self.assertEqual(tuple(result["checks"]), CHECK_NAMES)
            self.assertEqual(result["status"], "blocked")
            self.assertIn("responsive_pending", {item["code"] for item in result["issues"]})
            output = Path(raw) / "qa-report.md"
            write_report(result, output)
            self.assertIn("集中 QA", output.read_text(encoding="utf-8"))
