import unittest
import sys
from pathlib import Path

# Allow running tests without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    from d2r_agent.followups import build_followups
except ModuleNotFoundError as e:
    build_followups = None
    _import_err = e


class TestFollowupGeneration(unittest.TestCase):
    def setUp(self):
        if build_followups is None:
            self.skipTest(f"deps missing: {_import_err}")

    def test_missing_fields_generate_fixed_choices(self):
        fus = build_followups(missing_fields=["mode", "offline", "ladder_flag"], intent="runeword_recipe", entities=[])
        ids = {f.id for f in fus}
        self.assertIn("ctx_mode", ids)
        self.assertIn("ctx_offline", ids)
        self.assertIn("ctx_ladder_flag", ids)

        mode_fu = [f for f in fus if f.id == "ctx_mode"][0]
        self.assertFalse(mode_fu.allowFreeText)
        labels = [c.label for c in mode_fu.choices]
        self.assertIn("软核 SC", labels)
        self.assertIn("硬核 HC", labels)
        self.assertNotIn("其他/手动输入", labels)

    def test_build_compare_insight_spirit_generates_who_followup(self):
        fus = build_followups(missing_fields=[], intent="build_compare", entities=["Insight", "Spirit"])
        self.assertEqual(len([f for f in fus if f.id == "who"]), 1)
        who = [f for f in fus if f.id == "who"][0]
        labels = [c.label for c in who.choices]
        self.assertIn("给自己用", labels)
        self.assertIn("给米山用", labels)
        self.assertIn("不确定", labels)
        self.assertNotIn("其他/手动输入", labels)


if __name__ == "__main__":
    unittest.main()
