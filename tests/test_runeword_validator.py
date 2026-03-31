"""Tests for runeword_validator — P1 programmatic base/socket validation."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from d2r_agent.knowledge.runeword_validator import validate_runeword_base, format_validator_result

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "fact_db", "runewords.json")


class TestRunewordValidator(unittest.TestCase):
    def setUp(self):
        if not os.path.exists(DB_PATH):
            self.skipTest(f"runewords.json not found at {DB_PATH}")

    # ------------------------------------------------------------------
    # Spirit
    # ------------------------------------------------------------------
    def test_spirit_shield_4os_valid(self):
        r = validate_runeword_base("Spirit", "shield", 4, DB_PATH)
        self.assertTrue(r.valid)
        self.assertEqual(r.runeword_name, "Spirit")

    def test_spirit_sword_4os_valid(self):
        r = validate_runeword_base("Spirit", "sword", 4, DB_PATH)
        self.assertTrue(r.valid)

    def test_spirit_helm_invalid(self):
        r = validate_runeword_base("Spirit", "helm", None, DB_PATH)
        self.assertFalse(r.valid)
        self.assertIn("Spirit", r.reason)

    def test_spirit_shield_3os_invalid(self):
        r = validate_runeword_base("Spirit", "shield", 3, DB_PATH)
        self.assertFalse(r.valid)
        self.assertIn("4", r.reason)

    def test_spirit_zh_monarch_4os_valid(self):
        """鸢盾 (monarch shield) should resolve to shield category."""
        r = validate_runeword_base("Spirit", "鸢盾", 4, DB_PATH)
        self.assertTrue(r.valid)

    # ------------------------------------------------------------------
    # Insight
    # ------------------------------------------------------------------
    def test_insight_polearm_4os_valid(self):
        r = validate_runeword_base("Insight", "polearm", 4, DB_PATH)
        self.assertTrue(r.valid)

    def test_insight_staff_4os_valid(self):
        r = validate_runeword_base("Insight", "staff", 4, DB_PATH)
        self.assertTrue(r.valid)

    def test_insight_sword_invalid(self):
        r = validate_runeword_base("Insight", "sword", None, DB_PATH)
        self.assertFalse(r.valid)

    def test_insight_polearm_3os_invalid(self):
        r = validate_runeword_base("Insight", "polearm", 3, DB_PATH)
        self.assertFalse(r.valid)

    def test_insight_zh_alias(self):
        """眼光 Chinese alias should resolve Insight."""
        r = validate_runeword_base("眼光", None, None, DB_PATH)
        self.assertTrue(r.valid)
        self.assertEqual(r.runeword_name, "Insight")

    # ------------------------------------------------------------------
    # Infinity
    # ------------------------------------------------------------------
    def test_infinity_polearm_4os_valid(self):
        # Basin D2:RotW Infinity = Ber+Mal+Ist in 4-socket Polearm
        r = validate_runeword_base("Infinity", "polearm", 4, DB_PATH)
        self.assertTrue(r.valid)

    def test_infinity_zh_alias_base_check(self):
        r = validate_runeword_base("无极", "polearm", None, DB_PATH)
        self.assertTrue(r.valid)

    # ------------------------------------------------------------------
    # Base-only check (no socket)
    # ------------------------------------------------------------------
    def test_base_only_no_socket(self):
        r = validate_runeword_base("Spirit", "shield", None, DB_PATH)
        self.assertTrue(r.valid)
        self.assertIn(4, r.required_sockets)

    # ------------------------------------------------------------------
    # RW-only check (no base, no socket)
    # ------------------------------------------------------------------
    def test_rw_name_only(self):
        r = validate_runeword_base("Insight", None, None, DB_PATH)
        self.assertTrue(r.valid)
        self.assertGreater(len(r.all_variants), 0)

    # ------------------------------------------------------------------
    # Unknown runeword
    # ------------------------------------------------------------------
    def test_unknown_runeword(self):
        r = validate_runeword_base("NonExistentRW_XYZ", None, None, DB_PATH)
        self.assertFalse(r.valid)
        self.assertIn("未在 KB 中找到", r.reason)

    # ------------------------------------------------------------------
    # format_validator_result smoke test
    # ------------------------------------------------------------------
    def test_format_valid_result(self):
        r = validate_runeword_base("Insight", "polearm", 4, DB_PATH)
        out = format_validator_result(r)
        self.assertIn("✅", out)
        self.assertIn("Insight", out)

    def test_format_invalid_result_has_suggestion(self):
        r = validate_runeword_base("Spirit", "helm", None, DB_PATH)
        out = format_validator_result(r)
        self.assertIn("❌", out)
        self.assertIn("💡", out)

    # ------------------------------------------------------------------
    # Multi-variant coverage
    # ------------------------------------------------------------------
    def test_beast_axe_valid(self):
        r = validate_runeword_base("Beast", "axe", 5, DB_PATH)
        self.assertTrue(r.valid)

    def test_beast_scepter_valid(self):
        r = validate_runeword_base("Beast", "scepter", 5, DB_PATH)
        self.assertTrue(r.valid)

    def test_beast_shield_invalid(self):
        r = validate_runeword_base("Beast", "shield", None, DB_PATH)
        self.assertFalse(r.valid)

    # ------------------------------------------------------------------
    # required_sockets field
    # ------------------------------------------------------------------
    def test_required_sockets_populated(self):
        r = validate_runeword_base("Insight", None, None, DB_PATH)
        self.assertIn(4, r.required_sockets)

    def test_spirit_required_sockets_is_4(self):
        r = validate_runeword_base("Spirit", None, None, DB_PATH)
        self.assertEqual(r.required_sockets, [4])


if __name__ == "__main__":
    unittest.main()
