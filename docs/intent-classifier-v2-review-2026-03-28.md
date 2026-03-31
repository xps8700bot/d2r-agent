# d2r_agent intent classifier v2 review (2026-03-28)

## Verdict
**needs-fix**

The implementation is a solid and useful improvement over the prior rule-only behavior, and it appears to fix the motivating direct-answer failure for the Barbarian two-hand/one-hand case. However, I do **not** think it fully satisfies the v2 plan yet because two core plan promises remain under-verified / under-enforced:

1. the **LLM fallback path is not regression-tested in any meaningful way**; and
2. the fallback’s **“strict structured output schema” is only best-effort via prompting/parsing**, not actually enforced at the API boundary.

So: good implementation direction, good product improvement, but not ready for unconditional approval if the bar is “matches the full v2 plan.”

---

## Scope reviewed
Plan:
- `docs/intent-classifier-v2-plan-2026-03-28.md`

Implementation/docs reviewed:
- `src/d2r_agent/intent_classifier.py`
- `src/d2r_agent/telegram_render.py`
- `src/d2r_agent/detectors/context_gap.py`
- `src/d2r_agent/orchestrator.py`
- `src/d2r_agent/schemas.py`
- `telegram_bot.py`
- `tests/test_intent_classifier_v2.py`
- `docs/intent-classifier-v2-impl-2026-03-28.md`

Validation performed:
- Read code and compared against plan requirements.
- Ran `pytest -q tests/test_intent_classifier_v2.py` → **25 passed**.

---

## Strengths

### 1) The motivating routing bug is fixed in the right place
The core product bug was that queries like:
- `野蛮人怎么单手那双手武器`

previously fell through to `general`, preventing the mechanics-specific direct-answer path from running.

The new classifier fixes this at the **intent classification layer**, not by patching a later renderer/composer symptom. The relevant heuristic in `classify_intent_rules()`:
- `单手` + `双手` ⇒ `mechanics_claim`
- `双持` + interrogative modal ⇒ `mechanics_claim`

That is the correct architectural level for the fix.

### 2) Traceability is materially better and matches the spirit of the plan
`ClassificationResult` and `Trace` now carry:
- `rule_intent`
- `final_intent`
- `intent_source`
- `fallback_confidence`
- `fallback_reason_code`

`orchestrator.answer()` records these into trace output and also logs an `intent_classification_v2` event. This makes routing inspectable and debuggable, which was a major stated goal.

### 3) Direct-answer behavior for the main mechanics case is substantially improved
In `orchestrator._compose_answer()`:
- direct complete mechanics answers suppress options
- direct complete mechanics answers suppress `next_step_question`
- direct complete mechanics answers preserve a multi-line TL;DR instead of truncating it under `concise`

In `retrieval_router.py`, simple mechanics claims are explicitly routed as **no retrieval needed**, which supports fast direct answers.

In `telegram_render.py`, low-value hook lines are filtered from rendered output. This is a good defense-in-depth move even though the main fix is upstream.

### 4) Backward compatibility was handled reasonably
`context_gap.classify_intent()` remains as a rule-stage wrapper, which reduces the blast radius for existing callers/tests.

### 5) The new test file is focused and valuable
The new tests cover:
- rule-stable regressions
- targeted mechanics-claim fixes
- anti-regressions for build-advice/build-compare
- some traceability
- end-to-end answer behavior for the motivating case
- Telegram render hook suppression

That is meaningful product-oriented coverage, not just unit trivia.

---

## Issues / risks

### Issue 1 — The LLM fallback is not actually regression-tested
**Severity: high**

The plan explicitly calls for a two-stage classifier with an LLM fallback and regression coverage for routing behavior. The implementation includes `_call_llm_fallback()` and decision logic in `classify()`, but the new tests do **not** exercise the important fallback cases:
- rule returns `general` and fallback returns non-general/high → accepted
- rule returns `general` and fallback returns non-general/med → accepted
- rule returns `general` and fallback returns low → remains `general`
- rule returns `general` and fallback returns invalid JSON / invalid enum / transport failure → graceful degradation

Current tests only verify the no-API-key path (`general` stays `general`). That proves graceful disablement, but it does **not** prove that the actual v2 fallback behavior works.

This is the largest gap between “implemented” and “review-approved.”

### Issue 2 — The fallback schema is not “strict” in the way the plan describes
**Severity: medium-high**

The plan says the LLM fallback must return a **strict structured output schema**. In practice, the current code:
- sends a prompt asking for JSON
- reads free-form `chat/completions` text output
- strips code fences if present
- parses JSON afterward
- validates with Pydantic

This is useful, but it is not truly strict. The model is still free to emit prose, malformed JSON, or extra wrapper text. The code degrades safely, but the guarantee is weaker than the plan language.

If the provider supports structured output / JSON schema mode / response formatting, that should be used. If not, the review doc should at least state that the current behavior is “best-effort structured parsing,” not “strict schema enforcement.”

### Issue 3 — `FallbackClassification.intent` is not typed as an enum-like Literal
**Severity: medium**

`confidence` and `reason_code` are constrained Literals, but `intent` is plain `str`, with a post-parse membership check against `VALID_INTENTS`.

This works, but it is inconsistent with the stated schema strictness and makes the schema looser than necessary. A Literal or enum-backed field would make the model contract tighter and easier to reason about.

### Issue 4 — Direct-answer enforcement is strong for the motivating case, but edge-case coverage is still thin
**Severity: medium**

The product behavior is good for the exact core case and a couple nearby cases, but some edge cases are not verified:
- mechanics claims phrased in alternate wording that still reach `mechanics_claim`
- mechanics claims that are `high` confidence but not the specific Barbarian weapon pattern
- Telegram behavior with inline followups/markup in the full bot path, not just string rendering
- cases where future answer text changes slightly and no longer matches `HOOK_PATTERNS`

I do **not** see an immediate functional break here for the reviewed scenario, but I do see fragility risk.

### Issue 5 — The plan says fallback is for `general` and residual ambiguity, but the current implementation effectively solves the motivating cases via rules, not fallback
**Severity: low-medium**

This is not necessarily wrong — in fact, deterministic heuristics are preferable for known high-signal cases. But the implementation note emphasizes the new rule heuristic as the primary fix, while the plan presents fallback as a major v2 component for previously missed cases like:
- `野蛮人怎么单手那双手武器`
- `死灵能不能 levitate`

In practice, those examples are now mostly handled at rule stage, so the fallback remains important architecture but under-proven in real coverage.

---

## Does the implementation match the plan?

### What matches well
The implementation matches most of the plan’s structure:
- explicit rule-stage classifier: **yes**
- LLM fallback helper: **yes**
- final intent integrated into context-gap/orchestrator flow: **yes**
- downstream code uses final intent: **yes**
- traceability fields recorded: **yes**
- Telegram rendering suppresses hook language: **yes**
- regression tests for motivating routing and visible behavior: **partially yes**

### Where it does not fully match
1. **Strict fallback schema enforcement**: only partial / best-effort, not truly strict.
2. **Regression coverage for the fallback stage itself**: insufficient.
3. **Review bar for full v2 readiness**: not met yet if the plan is interpreted literally.

### Overall plan-match assessment
**Mostly matches the architectural plan, but not fully the verification/strictness bar described in the plan.**

---

## Are the tests adequate?

## Short answer
**Partially adequate, but not adequate for approving the full v2 design.**

### What the tests do well
The test file is strong on:
- rule-stage routing regressions
- the specific motivating mechanics-claim failure
- anti-regressions for build intent misclassification
- some orchestrator-level answer behavior
- Telegram render suppression

That is enough to support confidence that the **main product bug** was fixed.

### What is missing
To justify approval of “intent classifier v2” as planned, tests should also cover:
- mocked fallback acceptance (`general` → fallback high/med → final non-general)
- mocked fallback rejection (`general` → low → stay general)
- invalid fallback payload / parse failure / provider failure
- trace recording for real fallback cases (`intent_source == llm_fallback`, confidence/reason present)
- a full user-visible direct-answer regression for at least one fallback-driven classification path

Without these, the codebase has tests for the new heuristics and rendering, but not for the main new stage-2 contract.

---

## Direct-answer behavior assessment

## Motivating case: Barbarian one-handing a two-handed weapon
I believe the implementation **does enforce** the desired product behavior for the motivating case.

Why:
1. `classify_intent_rules()` now routes it to `mechanics_claim`.
2. `retrieval_router.route()` recognizes it as a simple direct mechanics claim and avoids retrieval.
3. `_compose_answer()` emits a direct three-part answer:
   - conclusion (`可以`)
   - boundary conditions (`不是所有双手武器都行`)
   - practical usage (`直接装备到单手位即可`)
4. `_is_direct_complete_answer` suppresses options and `next_step_question`.
5. `telegram_render.render_telegram_answer()` strips known hook lines if they somehow appear.

That aligns well with the product requirement.

## Likely edge cases
- `野蛮人可以单手拿双手剑吗` should behave correctly.
- `野蛮人双持可以吗` should likely behave correctly.
- `死灵能不能 levitate` will classify as `mechanics_claim`, but the answer branch is much more generic than the Barbarian-specific path; it may be acceptable, but it is not as clearly “complete direct answer” as the main case.

So I would say:
- **main direct-answer case:** good
- **nearby mechanics-claim cases:** probably okay
- **broad mechanics-claim family:** not yet demonstrated with the same confidence

---

## Recommended follow-up actions

### Must-do before approval
1. **Add mocked tests for the LLM fallback decision policy**
   - monkeypatch `_call_llm_fallback()`
   - cover accept/high, accept/med, reject/low, invalid/failure paths
   - verify resulting `ClassificationResult` fields and trace fields

2. **Tighten structured output enforcement for fallback**
   - use provider-native structured output / JSON mode / schema mode if available
   - if unavailable, at minimum document current behavior as best-effort rather than strict

3. **Constrain `FallbackClassification.intent` more tightly**
   - use Literal/enum if practical
   - avoid a loose `str` when the schema is supposed to be constrained

### Should-do next
4. **Add one end-to-end test for a fallback-driven classification path**
   - e.g. monkeypatch classifier fallback so a `general` query becomes `mechanics_claim`
   - verify final answer path and no-hook behavior

5. **Add a direct-answer test for `死灵能不能 levitate`**
   - confirm the user-visible behavior is acceptable, not just the intent label

6. **Make hook suppression less phrase-fragile**
   - optional: classify/suppress by section semantics or flags rather than only substring patterns

---

## Bottom line
This is a **good, real improvement** and it appears to fix the motivating Telegram/product issue. I would be comfortable saying the implementation is **directionally correct and mostly well done**.

But for the explicit v2 plan, I recommend **needs-fix** until:
- the fallback stage is properly tested, and
- the “strict structured output” claim is either made true in code or softened in docs.
