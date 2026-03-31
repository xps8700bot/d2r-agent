# Summary: Bot Fallback Bug Investigation — 2026-03-28

## Problem
Query `野蛮人怎么单手那双手武器` returns generic fallback:
> 我可以先给你一个可执行的解题/配装思路… 如果你要，我再继续细化…

instead of the direct answer that already exists in the codebase.

---

## Root Cause (confirmed)

**`classify_intent()` in `context_gap.py` returns `'general'` instead of `'mechanics_claim'`.**

The `mechanics_claim` intent has Chinese modal interrogative keywords (`能不能`, `可以吗`, `是否`) and English weapon terms (`one-hand`, `two-handed`), but **not** the Chinese weapon-mode words `单手` (one-handed) or `双手` (two-handed) by themselves.

The query uses natural phrasing — no modal verb, no English — so nothing matches and intent falls to `'general'`.

The downstream code in `_compose_answer()` and `retrieval_router.route()` both have **correct** logic for this case (string check `双手+单手` → direct answer, `need_retrieval=False`), but they are guarded by `elif intent == "mechanics_claim":` and therefore never execute.

**The correct answer code already exists. The routing never reaches it.**

---

## Secondary Issue

`telegram_bot.py` sets `ctx["concise"] = True`, but `orchestrator.answer()` does not forward this to `_compose_answer(concise=...)`. For the wrong-intent case this doesn't matter (the tldr is wrong regardless), but it means `options` and `next_q` are generated internally and only stripped later by `_render_telegram_answer`.

---

## Fix (one line in `classify_intent()`)

In `src/d2r_agent/detectors/context_gap.py`, inside `classify_intent()`, add before the `INTENT_RULES` loop:

```python
# Chinese weapon-mode mechanics: "one-hand a two-handed weapon" pattern
if ("单手" in q and "双手" in q) or "双持" in q:
    return "mechanics_claim"
```

Optional secondary: propagate `concise=bool(ctx.get("concise"))` when calling `_compose_answer()` in `answer()`.

---

## Docs Written

- `docs/telegram-direct-answer-investigation-2026-03-28.md` — Full investigation (symptom, reproduction, RCA, why previous fixes didn't work, solution options, test plan)
- `docs/telegram-direct-answer-investigation-2026-03-28-summary.md` — This file

## Recommended Next Action

**Apply the one-line fix to `classify_intent()` in `context_gap.py`**, then add a unit test asserting `classify_intent("野蛮人怎么单手那双手武器") == "mechanics_claim"` and an integration assertion that the answer contains `"可以"` and does not contain the fallback text.
