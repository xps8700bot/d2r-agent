"""Integration tests: orchestrator runeword_recipe intent + validator.

Tests verify that when the user query contains base-item info, the orchestrator:
1. Detects the base item / socket count via _extract_base_from_query
2. Calls validate_runeword_base and surfaces the result in the output

Also covers backward-compat: queries with NO base item info still work normally.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from d2r_agent.orchestrator import _extract_base_from_query
from d2r_agent.knowledge.runeword_validator import validate_runeword_base

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "fact_db", "runewords.json")


class TestExtractBaseFromQuery(unittest.TestCase):
    """Unit tests for the _extract_base_from_query helper."""

    def test_extract_cv_polearm(self):
        base, sockets = _extract_base_from_query("Infinity 四孔 CV")
        self.assertEqual(base, "polearm")
        self.assertEqual(sockets, 4)

    def test_extract_zh_monarch(self):
        base, sockets = _extract_base_from_query("Spirit 鸢盾 4 socket")
        self.assertEqual(base, "鸢盾")
        self.assertEqual(sockets, 4)

    def test_extract_zh_bow(self):
        base, sockets = _extract_base_from_query("Spirit 长弓 做法")
        self.assertEqual(base, "bow")

    def test_extract_no_base(self):
        """Query with no base item → (None, None)"""
        base, sockets = _extract_base_from_query("Infinity 符文顺序是什么")
        self.assertIsNone(base)

    def test_extract_socket_only_zh(self):
        base, sockets = _extract_base_from_query("Spirit 需要几孔？四孔吗")
        self.assertEqual(sockets, 4)

    def test_extract_eth_cv(self):
        base, sockets = _extract_base_from_query("Insight eth cv 四孔")
        self.assertEqual(base, "polearm")
        self.assertEqual(sockets, 4)


class TestValidatorDirectCalls(unittest.TestCase):
    """Direct validate_runeword_base calls matching the integration scenarios."""

    def setUp(self):
        if not os.path.exists(DB_PATH):
            self.skipTest(f"runewords.json not found at {DB_PATH}")

    def test_infinity_cv_4os_valid(self):
        """Infinity 四孔 CV → valid (CV = polearm)"""
        base, sockets = _extract_base_from_query("Infinity 四孔 CV")
        r = validate_runeword_base("Infinity", base, sockets, DB_PATH)
        self.assertTrue(r.valid, f"Expected valid, got: {r.reason}")

    def test_infinity_bow_invalid(self):
        """Infinity 四孔 长弓 → invalid (bow is not polearm)"""
        base, sockets = _extract_base_from_query("Infinity 四孔 长弓")
        self.assertEqual(base, "bow")
        r = validate_runeword_base("Infinity", base, sockets, DB_PATH)
        self.assertFalse(r.valid, f"Expected invalid for bow, got: {r.reason}")

    def test_spirit_monarch_valid(self):
        """Spirit 鸢盾 → valid"""
        base, sockets = _extract_base_from_query("Spirit 鸢盾 制作方法")
        self.assertEqual(base, "鸢盾")
        r = validate_runeword_base("Spirit", base, sockets, DB_PATH)
        self.assertTrue(r.valid, f"Expected valid, got: {r.reason}")

    def test_spirit_bow_invalid(self):
        """Spirit 长弓 → invalid (bow not a valid Spirit base)"""
        base, sockets = _extract_base_from_query("Spirit 长弓 怎么做")
        self.assertEqual(base, "bow")
        r = validate_runeword_base("Spirit", base, sockets, DB_PATH)
        self.assertFalse(r.valid, f"Expected invalid for bow, got: {r.reason}")

    def test_insight_eth_cv_valid(self):
        """Insight eth cv 四孔 → valid (cv = polearm, Insight accepts polearm)"""
        base, sockets = _extract_base_from_query("Insight eth cv 四孔")
        self.assertEqual(base, "polearm")
        self.assertEqual(sockets, 4)
        r = validate_runeword_base("Insight", base, sockets, DB_PATH)
        self.assertTrue(r.valid, f"Expected valid, got: {r.reason}")


class TestOrchestratorBackwardCompat(unittest.TestCase):
    """Ensure orchestrator.answer() still works for runeword queries WITHOUT base info."""

    def setUp(self):
        if not os.path.exists(DB_PATH):
            self.skipTest(f"runewords.json not found at {DB_PATH}")

    def test_runeword_no_base_info_returns_result(self):
        """Query without base info should still return answer (no crash, no validator warning)."""
        from d2r_agent.orchestrator import answer
        text, trace_path = answer("Infinity 符文顺序是什么")
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 0)
        # No validator warnings expected (no base in query)
        self.assertNotIn("⚠️", text)
        self.assertNotIn("底材不匹配", text)

    def test_runeword_with_valid_base_shows_checkmark(self):
        """Query with valid base should surface ✅ in output."""
        from d2r_agent.orchestrator import answer
        text, trace_path = answer("Infinity 四孔 CV 怎么做")
        self.assertIsInstance(text, str)
        self.assertIn("✅", text)

    def test_runeword_with_invalid_base_shows_cross(self):
        """Query with invalid base should surface ❌ in output."""
        from d2r_agent.orchestrator import answer
        text, trace_path = answer("Infinity 四孔 长弓 怎么做")
        self.assertIsInstance(text, str)
        self.assertIn("❌", text)


if __name__ == "__main__":
    unittest.main()
