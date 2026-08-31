from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

SCRIPTS = Path(__file__).parents[2] / "skills/lingguangzi-chapter-site/scripts"
sys.path.insert(0, str(SCRIPTS))

from chapter_types import Issue, read_json, write_json


class SharedTypeTests(unittest.TestCase):
    def test_issue_and_json_round_trip(self):
        with TemporaryDirectory() as raw:
            target = Path(raw) / "state.json"
            write_json(target, {"issues": [Issue("missing", "blocking", "缺少檔案", None).as_dict()]})
            self.assertEqual(read_json(target)["issues"][0]["severity"], "blocking")
