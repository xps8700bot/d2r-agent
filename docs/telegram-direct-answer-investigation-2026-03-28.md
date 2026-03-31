# Investigation: Bot Replies with Generic Fallback Instead of Direct Answer

**Date:** 2026-03-28  
**Investigator:** d2r_agent subagent  
**Status:** Root cause confirmed, solution ready to implement

---

## 1. Symptom

When a user sends the query:

> 野蛮人怎么单手那双手武器

The Telegram bot replies with generic fallback text:

> 我可以先给你一个可执行的解题/配装思路；涉及具体数值与掉落表时会要求检索证据。  
> 如果你要，我再继续细化：你希望我按'开荒低成本'还是'后期最优解'来回答？

**Expected behavior:** The bot should answer directly and completely, e.g.:

> 可以。野蛮人有职业特性，能把一部分双手近战武器当单手武器使用，所以才做得到双持。  
> 但不是所有双手武器都行：通常是双手剑，以及部分可被 Barb 单手化的双手近战武器；长柄、长枪、弓、弩这类不算。  
> 如果武器本身在 Barb 的可单手范围内，你直接装备到单手位即可，不需要额外操作或技能开关。

---

## 2. Reproduction Path

1. Start the Telegram bot (`python telegram_bot.py`)
2. Send the message: `野蛮人怎么单手那双手武器`
3. Observe: generic fallback reply is returned

**Confirmed programmatically:**

```python
# PYTHONPATH=src .venv/bin/python
from d2r_agent.detectors.context_gap import classify_intent
classify_intent('野蛮人怎么单手那双手武器')
# Returns: 'general'   ← WRONG
```

The full execution trace (with `concise=True` ctx from telegram_bot):
- `classify_intent()` → `'general'`
- `_compose_answer(..., intent='general', ...)` → falls into the default `else` branch → generic fallback tldr
- `_render_telegram_answer()` → strips `Options` and `Next step`, leaving only the tldr
- Final Telegram message: `我可以先给你一个可执行的解题/配装思路…`

---

## 3. Root Cause Analysis

### Root Cause 1 (Primary): Intent Classifier Misses Chinese-only `单手 + 双手` Pattern

**File:** `src/d2r_agent/detectors/context_gap.py`  
**Function:** `classify_intent(q: str) -> str`

The `mechanics_claim` intent is triggered by these keywords (see `INTENT_RULES`):

```python
("mechanics_claim", [
    "能不能",
    "可以吗",
    "是否",
    "被动",
    "passive",
    "one hand",
    "one-hand",
    "two hand",
    "two-hand",
    "two-handed",
    "levitate",
    "levitation",
]),
```

The query `野蛮人怎么单手那双手武器` contains:
- `单手` (one-handed) ✓
- `双手` (two-handed) ✓
- `野蛮人` (Barbarian) ✓

But **none** of the `mechanics_claim` keywords match because:
- There is no `能不能`, `可以吗`, or `是否` (modal/interrogative)
- Chinese words `单手` and `双手` are NOT in the keyword list
- English forms (`one hand`, `two-hand`, etc.) are not present

**Result:** `classify_intent` falls all the way through `INTENT_RULES` with no match, returning `'general'`.

### Root Cause 2 (Secondary): `_compose_answer` Mechanics Branch is Intent-Gated

**File:** `src/d2r_agent/orchestrator.py`  
**Function:** `_compose_answer()`  
**Lines:** ~220–245

Inside `_compose_answer`, there is a specific handling block for the `单手/双手` + Barbarian query:

```python
elif intent == "mechanics_claim":
    lowq = (user_query or "").lower()
    if ("双手" in user_query and "单手" in user_query) or ("two-handed weapon in one hand" in lowq):
        tldr.append("可以。野蛮人有职业特性…")
        tldr.append("但不是所有双手武器都行…")
        tldr.append("如果武器本身在 Barb 的可单手范围内…")
        confidence = "high"
```

This string check (`双手` + `单手` in query) would succeed for the user's query — **but it is guarded by `elif intent == "mechanics_claim"`**, which is never reached because `classify_intent()` returned `'general'`.

The same intent-gate exists in `retrieval_router.py`:

```python
# retrieval_router.py line 110–121
if intent == "mechanics_claim":
    simple_direct_claim = any([
        ("双手" in user_query and "单手" in user_query),
        ...
    ])
    if simple_direct_claim:
        return RetrievalRoute(need_retrieval=False, ...)
```

Again, this check is never reached for `intent='general'`.

### Root Cause 3 (Tertiary): `concise` ctx flag not propagated to `_compose_answer`

**File:** `src/d2r_agent/orchestrator.py`  
**Function:** `answer()` (line ~685)

`telegram_bot.py` sets `ctx["concise"] = True` to suppress follow-up hooks. However, `answer()` calls `_compose_answer()` without forwarding the `concise` parameter:

```python
# orchestrator.py line 685
ans0 = _compose_answer(user_query, ctx, gap.intent, rr.expected_entities, rr.need_retrieval, evidence, strategy_tldr=strategy_tldr)
# ^^^ concise=False (default) — ctx["concise"] is silently ignored
```

`_compose_answer` does accept `concise: bool = False`, but the caller never passes it. This means even if the intent were correct, the `options` and `next_step_question` would still be generated (though `_render_telegram_answer` in `telegram_bot.py` strips them from the final output). For the primary fallback case, `concise` only trims `options` and `next_q`, not the fallback `tldr` itself — so this is a minor secondary issue.

---

## 4. Exact Files and Functions Involved

| File | Function | Role in Bug |
|------|----------|-------------|
| `src/d2r_agent/detectors/context_gap.py` | `classify_intent()` | **Primary**: Missing `单手` + `双手` → `mechanics_claim` mapping |
| `src/d2r_agent/detectors/context_gap.py` | `INTENT_RULES` (data) | Missing Chinese one-handed/two-handed weapon keywords |
| `src/d2r_agent/orchestrator.py` | `_compose_answer()` | Has correct direct-answer logic but it's inside `elif intent == "mechanics_claim":` gate |
| `src/d2r_agent/retrieval_router.py` | `route()` | Has correct `need_retrieval=False` path for this case but it's inside `if intent == "mechanics_claim":` gate |
| `src/d2r_agent/orchestrator.py` | `answer()` | `concise` ctx key not forwarded to `_compose_answer()` |

---

## 5. Why Previous Fixes Did Not Solve It

### What was previously implemented

The code in `orchestrator.py` already has explicit handling for the Barbarian single-hand/dual-wield scenario:

```python
if ("双手" in user_query and "单手" in user_query) or ("two-handed weapon in one hand" in lowq):
    tldr.append("可以。野蛮人有职业特性…")
```

And `retrieval_router.py` has:

```python
simple_direct_claim = any([
    ("双手" in user_query and "单手" in user_query),
    ...
])
if simple_direct_claim:
    return RetrievalRoute(need_retrieval=False, ...)
```

These were likely added as part of an earlier fix attempt to make the bot answer directly for this case.

### Why they still fail

**The fix was applied in the wrong layer.** Both `_compose_answer` and `route()` do correct string-based matching on `双手 + 单手`, but they are only reached **after** `classify_intent()` has already determined the intent. Since these blocks are inside `elif intent == "mechanics_claim":` guards, they never execute when intent is `'general'`.

The fix was applied **downstream** of the classification decision. The classification itself — `classify_intent()` in `context_gap.py` — was never updated to recognize Chinese-only `单手+双手` patterns as `mechanics_claim`.

**In short:** The correct answer code exists, but the routing code never sends the query there.

---

## 6. Concrete Solution Options

### Option A (Recommended): Add Chinese keywords to `mechanics_claim` in `INTENT_RULES`

**File:** `src/d2r_agent/detectors/context_gap.py`

Add `"单手"` and `"双手"` (and optional `"野蛮人"` + weapon combos) to the `mechanics_claim` keyword list:

```python
("mechanics_claim", [
    "能不能",
    "可以吗",
    "是否",
    "被动",
    "passive",
    "one hand",
    "one-hand",
    "two hand",
    "two-hand",
    "two-handed",
    "levitate",
    "levitation",
    # ADD THESE:
    "单手",      # one-handed (any query mentioning one-handing will match)
    "双手",      # two-handed
    "双持",      # dual-wield
]),
```

**Pros:** Minimal change, directly addresses the classification miss.  
**Cons:** `单手` and `双手` are quite broad and might over-trigger for non-mechanic queries. Could be narrowed with co-occurrence checks.

**Variant A2 (more precise):** Add a custom rule before the keyword loop in `classify_intent()`:

```python
def classify_intent(q: str) -> str:
    s = q.lower()
    # ... existing 'build_compare' heuristic ...
    
    # ADD: Chinese dual-wield / weapon mode mechanics
    if ("单手" in q and "双手" in q) or "双持" in q:
        return "mechanics_claim"
    
    for intent, kws in INTENT_RULES:
        ...
```

This is more surgical: only triggers `mechanics_claim` when both `单手` and `双手` appear together (same co-occurrence check already used in the downstream code).

### Option B: Fix the intent gate in `_compose_answer` and `route()`

Instead of relying on `intent == "mechanics_claim"`, also check the string content for `general` intent:

```python
# In _compose_answer, in the default else branch:
else:
    lowq = (user_query or "").lower()
    # Barb single-hand mechanic: also handle for general intent (classification miss recovery)
    if ("双手" in user_query and "单手" in user_query) or "双持" in user_query:
        tldr.append("可以。野蛮人有职业特性…")
        ...
    else:
        tldr.append("我可以先给你一个可执行的解题/配装思路…")
```

**Pros:** Handles classification misses gracefully.  
**Cons:** Duplicates logic; adds complexity; doesn't fix the root cause; harder to maintain.

### Option C: Add a content-based intent override in `answer()`

In `orchestrator.answer()`, after calling `detect_context_gaps()`, add a post-classification override:

```python
gap = detect_context_gaps(user_query, user_ctx)
# Override: if 单手+双手 in query but intent is general, reclassify
if gap.intent == "general" and ("单手" in user_query and "双手" in user_query):
    gap = gap.model_copy(update={"intent": "mechanics_claim"})
```

**Pros:** Keeps `context_gap.py` clean; can be applied per query type without changing the keyword lists.  
**Cons:** Spreads classification logic across two places; harder to discover.

---

## 7. Recommended Implementation Plan

**Step 1 (Primary Fix): Apply Option A2 — add co-occurrence check in `classify_intent()`**

In `src/d2r_agent/detectors/context_gap.py`, in `classify_intent()`, add a guard before the `INTENT_RULES` loop:

```python
# After the build_compare heuristic, add:
# Chinese weapon-mode mechanics: "single-hand a two-handed weapon" pattern
if ("单手" in q and "双手" in q) or "双持" in q:
    return "mechanics_claim"
```

This is identical in spirit to the existing `build_compare` heuristic shortcut. It is minimal, targeted, and easy to test.

**Step 2 (Minor Fix): Propagate `concise` from ctx to `_compose_answer()`**

In `src/d2r_agent/orchestrator.py`, in `answer()`, change:

```python
ans0 = _compose_answer(user_query, ctx, gap.intent, rr.expected_entities, rr.need_retrieval, evidence, strategy_tldr=strategy_tldr)
```

to:

```python
ans0 = _compose_answer(user_query, ctx, gap.intent, rr.expected_entities, rr.need_retrieval, evidence, strategy_tldr=strategy_tldr, concise=bool(ctx.get("concise")))
```

This ensures telegram's `concise=True` actually strips `options` and `next_q` at the `_compose_answer` level too.

**Step 3 (Optional Cleanup): Also add `"双持"` as a `mechanics_claim` keyword in INTENT_RULES**

This makes the classification discoverable in the keyword table, not just in the heuristic shortcut.

---

## 8. Risks and Regression Concerns

### Risk 1: Over-triggering `mechanics_claim` for broad `单手`/`双手` mentions

- `单手` alone is rare in non-mechanic contexts in D2R queries
- The co-occurrence check (`单手` AND `双手`) is already used in `_compose_answer` with no reported FP issues
- Mitigation: use the co-occurrence form in `classify_intent()` too (Option A2), not individual keywords

### Risk 2: Existing tests that expect `general` for this query type

- Check `tests/` for any test that currently asserts `classify_intent('野蛮人怎么单手那双手武器') == 'general'`
- If such tests exist, they should be updated to expect `'mechanics_claim'`

### Risk 3: `mechanics_claim` MVI requirements

`MVI_FIELDS["mechanics_claim"] = []` — so reclassifying as `mechanics_claim` will NOT add any new `missing_fields`. This is correct: the Barb weapon wielding mechanic doesn't require session context.

### Risk 4: Retrieval router for the reclassified query

Once reclassified as `mechanics_claim`, `route()` will evaluate `simple_direct_claim`:
```python
simple_direct_claim = any([("双手" in user_query and "单手" in user_query), ...])
```
This will return `True` → `need_retrieval=False` → no live retrieval triggered. This is the desired behavior.

---

## 9. Test Plan

### Unit Tests (add to `tests/test_context_gap.py` or similar)

```python
def test_barb_single_hand_two_hand_classified_as_mechanics_claim():
    assert classify_intent("野蛮人怎么单手那双手武器") == "mechanics_claim"

def test_barb_dual_wield_classified_as_mechanics_claim():
    assert classify_intent("野蛮人双持") == "mechanics_claim"

def test_barb_wield_direct_answer():
    from d2r_agent.orchestrator import answer
    q = "野蛮人怎么单手那双手武器"
    ctx = {"release_track": "d2r_roitw", "season_id": "current", "mode": "SC",
           "ladder_flag": "non-ladder", "offline": False, "concise": True}
    out, _ = answer(q, ctx)
    # Must contain the direct answer, not the fallback
    assert "可以" in out or "野蛮人" in out
    assert "我可以先给你一个可执行的解题" not in out
    assert "如果你要" not in out
```

### Integration Test (Telegram bot behavior)

After applying fixes:
1. Start bot
2. Send: `野蛮人怎么单手那双手武器`
3. Expected reply includes: "可以。野蛮人有职业特性…"
4. No follow-up hooks (no "如果你要", no "你希望我按'开荒低成本'")

### Regression Check

Run existing test suite:
```bash
cd d2r_agent && PYTHONPATH=src .venv/bin/pytest tests/ -q
```

Ensure no regressions in:
- `test_followups.py`
- `test_interactive_session.py`
- Any test asserting on `classify_intent` output for existing queries

---

## 10. Related Files for Context

- `notes/necro_onehand_twohand_basin_note.md` — earlier research establishing that Barb (not Necro) can one-hand two-handed swords; the bot has this knowledge
- `test_runs_after_phase0_1.txt`, `test_runs_after_phase0_2.txt` — historical test runs showing this query type was tested
- `data/telegram_memory/chat_6222114811.jsonl` — production logs showing 3 occurrences of the fallback reply for this pattern

---

*Investigation completed 2026-03-28. No code modified.*
