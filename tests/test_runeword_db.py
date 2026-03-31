"""Tests for the structured runeword KB (data/fact_db/runewords.json)."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from d2r_agent.knowledge.runeword_db import search_runewords, format_runeword_hit

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "fact_db", "runewords.json")


class TestRunewordDB(unittest.TestCase):
    def setUp(self):
        if not os.path.exists(DB_PATH):
            self.skipTest(f"runewords.json not found at {DB_PATH}")

    def test_insight_by_english(self):
        hits = search_runewords("Insight runeword recipe", path=DB_PATH, limit=3)
        names = [h.entry.name for h in hits]
        self.assertIn("Insight", names, "Insight should be found by English name")

    def test_insight_by_chinese_alias(self):
        hits = search_runewords("眼光符文顺序", path=DB_PATH, limit=3)
        names = [h.entry.name for h in hits]
        self.assertIn("Insight", names, "Insight should be found via Chinese alias 眼光")

    def test_spirit_by_chinese_alias(self):
        hits = search_runewords("精神盾符文", path=DB_PATH, limit=3)
        names = [h.entry.name for h in hits]
        self.assertIn("Spirit", names, "Spirit should be found via Chinese alias 精神")

    def test_insight_variant_item_types(self):
        hits = search_runewords("Insight", path=DB_PATH, limit=1)
        self.assertTrue(len(hits) > 0)
        item_types = {v.item_type for v in hits[0].entry.variants}
        self.assertIn("Polearm", item_types)
        self.assertIn("Staff", item_types)

    def test_spirit_rune_order(self):
        hits = search_runewords("Spirit", path=DB_PATH, limit=1)
        self.assertTrue(len(hits) > 0)
        rune_orders = {v.rune_order for v in hits[0].entry.variants}
        # Should contain Tal+Thul+Ort+Amn in some form
        combined = " ".join(rune_orders)
        self.assertIn("Tal", combined)
        self.assertIn("Thul", combined)
        self.assertIn("Ort", combined)
        self.assertIn("Amn", combined)

    def test_format_runeword_hit(self):
        hits = search_runewords("Insight", path=DB_PATH, limit=1)
        self.assertTrue(len(hits) > 0)
        formatted = format_runeword_hit(hits[0])
        self.assertIn("Insight", formatted)
        self.assertIn("theamazonbasin.com", formatted)

    def test_infinity_alias(self):
        hits = search_runewords("无极", path=DB_PATH, limit=3)
        names = [h.entry.name for h in hits]
        self.assertIn("Infinity", names, "Infinity should be found via Chinese alias 无极")

    def test_total_runewords_count(self):
        from d2r_agent.knowledge.runeword_db import _load_runewords
        entries = _load_runewords(DB_PATH)
        self.assertGreaterEqual(len(entries), 100, "Should have at least 100 runewords (Basin full set)")

    # ── Extended Chinese alias tests (Part A expansion) ──────────────────

    def test_enigma_alias_miju(self):
        hits = search_runewords("谜语符文", path=DB_PATH, limit=3)
        names = [h.entry.name for h in hits]
        self.assertIn("Enigma", names, "Enigma should be found via alias 谜语")

    def test_call_to_arms_alias_cta(self):
        hits = search_runewords("CTA 武器", path=DB_PATH, limit=3)
        names = [h.entry.name for h in hits]
        self.assertIn("Call to Arms", names, "Call to Arms should be found via alias CTA")

    def test_chains_of_honor_alias(self):
        hits = search_runewords("荣誉锁链 护甲", path=DB_PATH, limit=3)
        names = [h.entry.name for h in hits]
        self.assertIn("Chains of Honor", names, "Chains of Honor should be found via alias 荣誉锁链")

    def test_heart_of_the_oak_alias_hoto(self):
        hits = search_runewords("hoto 法杖", path=DB_PATH, limit=3)
        names = [h.entry.name for h in hits]
        self.assertIn("Heart of the Oak", names, "Heart of the Oak should be found via alias hoto")

    def test_grief_alias_aotong(self):
        hits = search_runewords("哀恸剑", path=DB_PATH, limit=3)
        names = [h.entry.name for h in hits]
        self.assertIn("Grief", names, "Grief should be found via alias 哀恸")

    def test_breath_of_the_dying_alias(self):
        hits = search_runewords("亡者之息武器", path=DB_PATH, limit=3)
        names = [h.entry.name for h in hits]
        self.assertIn("Breath of the Dying", names, "Breath of the Dying should be found via alias 亡者之息")

    def test_beast_alias_yeshou(self):
        hits = search_runewords("野兽斧", path=DB_PATH, limit=3)
        names = [h.entry.name for h in hits]
        self.assertIn("Beast", names, "Beast should be found via alias 野兽")

    def test_lawbringer_alias(self):
        hits = search_runewords("执法者剑", path=DB_PATH, limit=3)
        names = [h.entry.name for h in hits]
        self.assertIn("Lawbringer", names, "Lawbringer should be found via alias 执法者")

    def test_obedience_alias_shuncong(self):
        hits = search_runewords("顺服长矛", path=DB_PATH, limit=3)
        names = [h.entry.name for h in hits]
        self.assertIn("Obedience", names, "Obedience should be found via alias 顺服")


if __name__ == "__main__":
    unittest.main()
