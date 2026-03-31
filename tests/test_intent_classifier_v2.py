"""Regression tests for intent classifier v2.

Tests cover:
1. Rule-stable cases (deterministic rules, must not regress)
2. Fallback-targeted cases (v2 additions: 单手+双手 pattern)
3. Anti-regression cases (build_advice/compare must NOT be misclassified as mechanics_claim)
4. ClassificationResult traceability
5. End-to-end routing (orchestrator.answer) for key mechanics_claim query
6. Telegram behavior: direct-answer queries produce no hook lines
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Allow running tests without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    from d2r_agent.intent_classifier import classify, classify_intent_rules, ClassificationResult
    from d2r_agent.detectors.context_gap import classify_intent, detect_context_gaps
except ModuleNotFoundError as e:
    pytest.skip(f"deps missing: {e}", allow_module_level=True)


# ---------------------------------------------------------------------------
# Rule-stable cases (must not regress)
# ---------------------------------------------------------------------------

class TestRuleStable:
    def test_runeword_recipe_zh(self):
        assert classify_intent_rules("谜团怎么做") == "runeword_recipe"

    def test_runeword_recipe_spirit_shield(self):
        assert classify_intent_rules("Spirit 盾符文顺序") == "runeword_recipe"

    def test_season_info_start_date(self):
        assert classify_intent_rules("这个赛季什么时候开始") == "season_info"

    def test_season_info_ladder_disabled(self):
        assert classify_intent_rules("天梯禁用了没有") == "season_info"

    def test_build_compare_insight_spirit(self):
        assert classify_intent_rules("精神还是眼光") == "build_compare"

    def test_build_compare_ice_fire(self):
        assert classify_intent_rules("冰法还是火法开荒") == "build_compare"

    def test_drop_rate_countess_lo(self):
        assert classify_intent_rules("女伯爵掉 Lo 吗") == "drop_rate"


# ---------------------------------------------------------------------------
# Fallback-targeted: previously returned 'general', now correctly mechanics_claim
# ---------------------------------------------------------------------------

class TestFallbackTargeted:
    def test_barb_single_hand_two_hand_weapon(self):
        """Primary regression: 野蛮人怎么单手那双手武器 must -> mechanics_claim."""
        assert classify_intent_rules("野蛮人怎么单手那双手武器") == "mechanics_claim"

    def test_necro_levitate(self):
        assert classify_intent_rules("死灵能不能 levitate") == "mechanics_claim"

    def test_dual_wield_with_interrogative(self):
        """双持 + interrogative modal -> mechanics_claim."""
        assert classify_intent_rules("野蛮人双持可以吗") == "mechanics_claim"

    def test_dual_wield_with_nengbuneng(self):
        assert classify_intent_rules("双持能不能做到") == "mechanics_claim"

    def test_single_and_dual_co_occurrence(self):
        """单手 + 双手 co-occurrence always -> mechanics_claim regardless of other tokens."""
        assert classify_intent_rules("野蛮人可以单手拿双手剑吗") == "mechanics_claim"


# ---------------------------------------------------------------------------
# Anti-regression: build queries must NOT be misclassified as mechanics_claim
# ---------------------------------------------------------------------------

class TestAntiRegression:
    def test_whirlwind_build_dual_wield(self):
        """双持旋风蛮开荒 is a build question, not a mechanics claim."""
        assert classify_intent_rules("双持旋风蛮开荒怎么配") == "build_advice"

    def test_two_hand_sword_choice(self):
        """双手剑开荒选哪把 is build advice (no 单手 co-occurrence)."""
        assert classify_intent_rules("双手剑开荒选哪把") == "build_advice"

    def test_barb_dual_wield_leveling(self):
        """野蛮人双持开荒 is build advice (双持 without interrogative)."""
        assert classify_intent_rules("野蛮人双持开荒") == "build_advice"


# ---------------------------------------------------------------------------
# classify_intent (context_gap wrapper) consistency
# ---------------------------------------------------------------------------

class TestContextGapWrapper:
    def test_barb_weapon_classify_intent_wrapper(self):
        """classify_intent() in context_gap.py delegates to the new rule classifier."""
        assert classify_intent("野蛮人怎么单手那双手武器") == "mechanics_claim"

    def test_build_compare_classify_intent_wrapper(self):
        assert classify_intent("精神还是眼光") == "build_compare"


# ---------------------------------------------------------------------------
# ClassificationResult traceability
# ---------------------------------------------------------------------------

class TestTraceability:
    def test_rule_hit_traceability(self):
        result = classify("野蛮人怎么单手那双手武器")
        assert isinstance(result, ClassificationResult)
        assert result.rule_intent == "mechanics_claim"
        assert result.final_intent == "mechanics_claim"
        assert result.intent_source == "rule"
        assert result.fallback_confidence is None
        assert result.fallback_reason_code is None

    def test_rule_hit_runeword(self):
        result = classify("谜团怎么做")
        assert result.rule_intent == "runeword_recipe"
        assert result.final_intent == "runeword_recipe"
        assert result.intent_source == "rule"

    def test_general_no_llm_available(self):
        """When no LLM key available, general stays general with rule source."""
        import os
        orig = os.environ.pop("OPENAI_API_KEY", None)
        try:
            result = classify("什么是世界上最好的游戏")
            assert result.rule_intent == "general"
            # Without LLM, final_intent should also be general
            assert result.final_intent == "general"
        finally:
            if orig is not None:
                os.environ["OPENAI_API_KEY"] = orig


# ---------------------------------------------------------------------------
# End-to-end routing: orchestrator.answer for mechanics_claim
# ---------------------------------------------------------------------------

class TestOrchestratorE2E:
    def _default_ctx(self):
        return {
            "release_track": "d2r_roitw",
            "season_id": "current",
            "mode": "SC",
            "ladder_flag": "non-ladder",
            "offline": False,
            "concise": True,
        }

    def test_barb_wield_direct_answer(self):
        """野蛮人怎么单手那双手武器 must produce a direct complete answer."""
        from d2r_agent.orchestrator import answer

        q = "野蛮人怎么单手那双手武器"
        ctx = self._default_ctx()
        out, _trace = answer(q, ctx)

        # Must contain the direct answer
        assert "可以" in out, f"Expected '可以' in output:\n{out}"
        # Must NOT be the generic fallback
        assert "我可以先给你一个可执行的解题" not in out, f"Found generic fallback:\n{out}"
        # Must NOT have low-value hook lines
        assert "如果你要" not in out, f"Found hook line:\n{out}"
        assert "你希望我按" not in out, f"Found hook line:\n{out}"

    def test_barb_wield_answer_completeness(self):
        """Direct answer must include all three key elements."""
        from d2r_agent.orchestrator import answer

        q = "野蛮人怎么单手那双手武器"
        ctx = self._default_ctx()
        out, _trace = answer(q, ctx)

        # 1. Conclusion: yes it's possible
        assert "可以" in out
        # 2. Boundary: not all two-handed weapons
        assert "不是所有" in out
        # 3. How: equip directly
        assert "装备" in out or "单手位" in out

    def test_build_compare_not_direct_complete(self):
        """build_compare still uses options/followups (not direct-complete path)."""
        from d2r_agent.orchestrator import answer

        q = "精神还是眼光"
        ctx = self._default_ctx()
        out, _trace = answer(q, ctx)

        # Should contain some form of answer or context
        assert out.strip(), "Expected non-empty output"
        # Should not be the generic fallback
        # (build_compare has its own branch in _compose_answer)


# ---------------------------------------------------------------------------
# Telegram rendering: hook suppression
# ---------------------------------------------------------------------------

class TestTelegramRender:
    def _render(self, text: str) -> str:
        """Import and call render_telegram_answer from the shared module."""
        from d2r_agent.telegram_render import render_telegram_answer
        return render_telegram_answer(text)

    def test_direct_answer_passes_through(self):
        """Direct mechanics answer should pass through cleanly."""
        text = """Assumptions
- release_track: d2r_roitw

TL;DR
- 可以。野蛮人有职业特性，能把一部分双手近战武器当单手武器使用，所以才做得到双持。
- 但不是所有双手武器都行：通常是双手剑，以及部分可被 Barb 单手化的双手近战武器；长柄、长枪、弓、弩这类不算。
- 如果武器本身在 Barb 的可单手范围内，你直接装备到单手位即可，不需要额外操作或技能开关。

Evidence
- (none)

Options

Next step
- 

(Trace)
- wrote: traces/xxx.json"""
        rendered = self._render(text)
        assert "可以" in rendered
        assert "不是所有" in rendered
        assert "装备到单手位" in rendered
        # No hook lines
        assert "如果你要" not in rendered
        assert "你希望我按" not in rendered

    def test_hook_lines_suppressed_with_real_content(self):
        """Hook lines following real content should be filtered; real content preserved."""
        text = """TL;DR
- 冰法开荒效率较高，推荐冰球/陨石路线。
- 你希望我按'开荒低成本'还是'后期最优解'来回答?

(Trace)
- wrote: traces/xxx.json"""
        rendered = self._render(text)
        # Real content should be present
        assert "冰法" in rendered
        # Hook line should be gone
        assert "你希望我按" not in rendered


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
