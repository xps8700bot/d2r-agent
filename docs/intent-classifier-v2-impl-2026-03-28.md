# d2r_agent intent classifier v2 — implementation notes (2026-03-28)

## Status: IMPLEMENTED

Plan doc: `docs/intent-classifier-v2-plan-2026-03-28.md`
Investigation doc: `docs/telegram-direct-answer-investigation-2026-03-28.md`

---

## What was built

### New module: `src/d2r_agent/intent_classifier.py`

Core two-stage classifier:

1. **Stage 1 — deterministic rule classifier** (`classify_intent_rules(q)`):
   - Keyword matching on `INTENT_RULES` (same intents as before, slightly updated)
   - Two special co-occurrence heuristics evaluated before the keyword loop:
     - `还是 / vs / 对比` → `build_compare`
     - `单手 + 双手` (co-occurrence) → `mechanics_claim`
     - `双持 + interrogative modal` (能不能/可以吗/是否/可以) → `mechanics_claim`
   - `双持` alone (e.g., in "双持旋风蛮开荒") remains `build_advice` (no false positive)

2. **Stage 2 — LLM fallback** (`_call_llm_fallback(q)`):
   - Triggered only when Stage 1 returns `general`
   - Calls OpenAI-compatible API (env: `OPENAI_API_KEY`, optional `OPENAI_BASE_URL`, `D2R_INTENT_MODEL`)
   - Returns constrained `FallbackClassification` with `intent`, `confidence`, `reason_code`, `needs_review`
   - Gracefully degrades (returns `None`) when API key not set or call fails

3. **Decision policy** (`classify(q) -> ClassificationResult`):
   - Strong rule hit → accept, no LLM call
   - Rule returns `general` → invoke LLM fallback
   - LLM returns non-general + high/med confidence → accept
   - LLM returns low confidence or general → keep `general`

4. **Traceability**: `ClassificationResult` records:
   - `rule_intent`: what the rule stage returned
   - `final_intent`: the intent used downstream
   - `intent_source`: `"rule"` or `"llm_fallback"`
   - `fallback_confidence`: only set when LLM was used
   - `fallback_reason_code`: enum from `FallbackReasonCode`

### New module: `src/d2r_agent/telegram_render.py`

Extracted `render_telegram_answer()` from `telegram_bot.py` for testability.  
Adds `HOOK_PATTERNS` filtering — suppresses low-value follow-up hook lines when
real content is present:

```python
HOOK_PATTERNS = [
    "如果你要，我再继续",
    "如果你要，我可以继续",
    "你希望我按",
    "你想让我继续",
    "我可以先给你一个可执行的解题",
    "需要你先确认",
]
```

### Modified: `src/d2r_agent/detectors/context_gap.py`

- `INTENT_RULES` and old `classify_intent()` body removed; delegated to `intent_classifier.py`
- `classify_intent()` kept as backward-compat wrapper (tests that call it directly still work)
- `classify_intent_v2()` added as public two-stage wrapper
- `detect_context_gaps()` accepts `_classification` param to reuse pre-computed result

### Modified: `src/d2r_agent/orchestrator.py`

- `answer()` runs `classify()` first (before `detect_context_gaps`)
- Passes `_classification` to avoid double classification
- Records traceability in `Trace` object: `rule_intent`, `final_intent`, `intent_source`,
  `fallback_confidence`, `fallback_reason_code`
- **Fixed `concise` bug**: `ctx["concise"]` now forwarded to `_compose_answer()`
- Direct complete answers (`intent == mechanics_claim`, `confidence == high`, `len(tldr) >= 3`):
  - `options = []` (no A/B/C options)
  - `next_step_question = ""` (no hook question)
  - `tldr` is preserved intact (no truncation)

### Modified: `src/d2r_agent/schemas.py`

`Trace` now includes intent v2 traceability fields:
```python
rule_intent: str = ""
final_intent: str = ""
intent_source: str = "rule"
fallback_confidence: Optional[str] = None
fallback_reason_code: Optional[str] = None
```

### Modified: `telegram_bot.py`

- Imports `render_telegram_answer` from `telegram_render`
- `_render_telegram_answer()` delegates to shared module

---

## Root cause fixed

**Primary bug**: `classify_intent("野蛮人怎么单手那双手武器")` returned `"general"`.

The query contains `单手` (one-hand) + `双手` (two-hand) — a co-occurrence pattern that
unambiguously signals a weapon-mode mechanics question. This pattern was checked
*downstream* in `_compose_answer` and `retrieval_router`, but only behind an
`if intent == "mechanics_claim":` gate. Since the gate was never reached
(intent was `general`), the direct-answer logic never ran.

**Fix**: Added co-occurrence heuristic in `classify_intent_rules()`, evaluated before
the keyword loop. Now routes correctly to `mechanics_claim`.

---

## Test coverage

`tests/test_intent_classifier_v2.py` — 25 tests covering:
- Rule-stable cases (7 tests): must not regress
- Fallback-targeted cases (5 tests): previously returned `general`, now `mechanics_claim`
- Anti-regression cases (3 tests): `双持旋风蛮开荒` and similar must remain `build_advice`
- Context gap wrapper (2 tests): backward compat
- Traceability (3 tests): `ClassificationResult` fields
- End-to-end orchestrator (3 tests): full answer with direct-answer checks
- Telegram rendering (2 tests): hook suppression

**All 165 tests pass (0 regressions).**

---

## Commit

`eca37e2` — feat: intent classifier v2 — rule-first + LLM fallback + traceability

---

## Not implemented (future work)

- LLM fallback is implemented but requires `OPENAI_API_KEY` env var; not auto-activated.
  It gracefully degrades to `general` when unavailable. This is intentional for offline/test safety.
- Low-confidence fallback result promotion: currently kept as `general`. Future extension
  could use a review queue or UI flag.
- Interactive review flow for `fallback_needs_review=True` results.
