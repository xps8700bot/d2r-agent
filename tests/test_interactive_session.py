import unittest
import sys
from pathlib import Path

# Allow running tests without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from d2r_agent.interactive_session import simulate_interactive_flow


class TestInteractiveSessionSimulation(unittest.TestCase):
    def test_simulation_fills_missing_fields_and_appends_followup(self):
        calls = []

        def fake_answer(q: str, ctx: dict, interactive_used: bool):
            calls.append((q, dict(ctx), interactive_used))
            # First run: requires mode, has a next-step question.
            if len(calls) == 1:
                return (
                    "OUT1\nNext step\n- who?",
                    {"missing_fields": ["mode"], "questions_to_ask": ["mode?"], "next_step_question": "who?"},
                )
            # Second run: resolved.
            return ("OUT2", {"missing_fields": [], "questions_to_ask": [], "next_step_question": None})

        out, ctx = simulate_interactive_flow(
            initial_query="compare A vs B",
            initial_ctx={},
            scripted_inputs=["SC", "self"],
            answer_fn=fake_answer,
        )

        self.assertEqual(out, "OUT2")
        self.assertEqual(ctx.get("mode"), "SC")
        self.assertTrue(isinstance(ctx.get("_followups"), list))
        self.assertEqual(ctx["_followups"][0]["a"], "self")


if __name__ == "__main__":
    unittest.main()
