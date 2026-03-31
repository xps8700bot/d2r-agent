# Review: Telegram Direct-Answer Bug Investigation — 2026-03-28

**Reviewer:** review subagent  
**Date:** 2026-03-28  
**Scope:** Review of investigation and proposed fix for query `野蛮人怎么单手那双手武器` returning Telegram fallback instead of a direct answer.  
**Verdict:** **needs revision**

---

## 1) Review verdict

**Needs revision.**

The investigation correctly identifies the *primary routing bug* and the proposed classifier change would very likely fix the reported Telegram symptom for this exact query. However, the write-up overstates certainty in a few places, leaves product/coverage risks underexplored, and treats a narrow heuristic as if it were a complete fix plan. The one-line fix is **sufficient for the current symptom path**, but **only as a partial fix** from a product and regression perspective.

---

## 2) What is correct in the investigation

### A. Primary root cause is real and independently verified
I independently verified the current behavior in code/runtime:

- `classify_intent("野蛮人怎么单手那双手武器")` currently returns `general`
- `answer()` then routes through the generic non-retrieval / general-answer path
- output becomes the generic fallback instead of the direct mechanic answer

This matches the investigation’s main claim.

### B. Downstream direct-answer logic already exists
The investigation is correct that there is already downstream logic for this pattern:

- `orchestrator._compose_answer(..., intent="mechanics_claim", ...)` contains a specific branch for queries containing `双手` + `单手`
- `retrieval_router.route()` also has a `mechanics_claim` branch that sets `need_retrieval=False` for simple direct mechanic claims, including this pattern

So the failure is not that the answer content is missing. The routing simply never reaches it.

### C. Intent gating is the key reason the existing fix did not fire
This part of the investigation is accurate: earlier logic was added too far downstream. Because both direct-answer and no-retrieval behavior sit behind `intent == "mechanics_claim"`, a misclassification to `general` defeats both.

### D. `concise` propagation issue is real
`answer()` does not pass `concise=bool(ctx.get("concise"))` into `_compose_answer()`, while `telegram_bot.py` does set `ctx["concise"] = True`.

That is a real code issue.

### E. Telegram rendering hides some of the impact
I verified `telegram_bot.py` has `_render_telegram_answer()` that collapses the CLI-style output and skips `Options`, while using TL;DR / Evidence / Next-step sections. So for Telegram specifically, the missing `concise` propagation is not the reason this bug manifests.

---

## 3) What is incomplete / risky / possibly wrong

### A. The proposed fix is too broad if presented as a general rule
The suggested rule:

```python
if ("单手" in q and "双手" in q) or "双持" in q:
    return "mechanics_claim"
```

is probably acceptable as an emergency heuristic, but it is broader than the investigation acknowledges:

- `双持` is not always a mechanics-claim question; it may appear in build advice, weapon choice, or style discussions
- `单手` + `双手` can appear in recommendation/comparison queries, not only rule-claim queries

This does **not** make the fix wrong, but it means the investigation should describe it as a **targeted heuristic with potential over-classification**, not as a universally clean semantic mapping.

### B. The write-up does not distinguish “sufficient for this bug” vs “sufficient for product quality” clearly enough
For the specific Telegram symptom, the classifier fix is likely enough.

For broader product fit, it is only partial because:

- it fixes one phrasing family, not the general Chinese mechanics-question gap
- it hardcodes surface strings instead of improving the intent model structure
- it does not add regression coverage for nearby natural Chinese phrasings

### C. The investigation assumes answer correctness without reviewing factual quality deeply enough
The proposed direct answer says, in effect, Barb can one-hand some two-handed melee weapons, typically two-handed swords, not polearms/spears/bows/crossbows.

That answer is directionally plausible and likely aligned with intended product behavior, but the investigation did not separately validate whether the exact wording matches the project’s evidence policy / mechanics source standards. Since this code path answers without retrieval, the factual content should be reviewed with the same care as the routing logic.

### D. Test plan is too narrow on classifier behavior
The suggested tests focus on:

- this exact Chinese query
- a bare `野蛮人双持`
- one end-to-end answer assertion

Missing are tests for false positives / boundary cases, e.g.:

- build/advice queries that include `双持`
- comparison queries containing both `单手` and `双手`
- other Chinese mechanics phrasings like `野蛮人为什么可以双持双手剑` / `野蛮人能把双手剑当单手吗`

### E. “Root cause confirmed, solution ready to implement” is too strong as written
The root cause is confirmed, yes. But “solution ready” suggests review completeness that is not fully there. It is more accurate to say:

- root cause confirmed
- minimal fix identified
- broader coverage / regression plan still needs tightening

---

## 4) Is the proposed fix sufficient?

## Short answer

**For the exact Telegram bug report: yes, likely sufficient.**  
**For the broader product/problem space: no, only partial.**

## Why it is sufficient for the current symptom
Once this query is reclassified to `mechanics_claim`:

1. `retrieval_router.route()` will hit `simple_direct_claim`
2. `need_retrieval` will become `False`
3. `_compose_answer()` will enter the existing mechanics-claim branch
4. the TL;DR will become the intended direct answer
5. `telegram_bot._render_telegram_answer()` will render that TL;DR into the Telegram reply

That means the reported user-visible failure should be corrected without touching production answer text.

## Why it is only partial overall
Because the fix is a narrow lexical override, not a robust expansion of Chinese intent understanding. It handles one family of wording but does not prove the broader mechanics-claim detection is healthy.

---

## 5) Recommended amendments to the plan

### Amendment 1: Reframe the fix as a targeted hotfix, not a complete semantic solution
Recommend documenting it as:

- **hotfix scope:** restore direct answer for known Chinese Barb wielding phrasing
- **follow-up scope:** review Chinese mechanics-claim heuristics more systematically

### Amendment 2: Prefer the co-occurrence rule over adding raw keywords into `INTENT_RULES`
I agree with the investigation that the co-occurrence heuristic is safer than simply appending `单手` / `双手` as standalone keywords.

So if implementing now, prefer:

```python
if ("单手" in q and "双手" in q) or "双持" in q:
    return "mechanics_claim"
```

—but the review should explicitly label `"双持"` as the riskier half of that heuristic.

A safer variant would be to narrow `双持` with class/mechanics context, for example requiring one of:

- `野蛮人`
- weapon wording
- question framing such as `能不能 / 可以 / 怎么 / 是否`

### Amendment 3: Add a regression matrix, not just one happy-path test
At minimum, add tests for:

**Positive cases**
- `野蛮人怎么单手那双手武器`
- `野蛮人能把双手剑当单手吗`
- `野蛮人为什么能双持双手剑`

**Boundary / negative cases**
- a build-advice query mentioning `双持`
- a comparison query with `单手` vs `双手`
- a non-mechanics general query containing `双持`

### Amendment 4: Treat `concise` forwarding as cleanup, not part of the root-cause fix
This should remain in the review as a valid secondary issue, but it should be clearly separated from the direct-answer bug itself.

Suggested phrasing:
- **bug fix:** classifier hotfix
- **cleanup:** propagate `concise` correctly for consistency across renderers

### Amendment 5: Validate the canned mechanics answer against product policy
Before shipping, confirm the existing direct-answer text is acceptable under the project’s evidence/rule-answer policy for non-retrieval mechanic claims.

---

## 6) Regression / test concerns

### A. Classifier overreach
Main regression risk is reclassifying queries to `mechanics_claim` that would have been better handled as:

- `build_advice`
- `build_compare`
- `general`

This is especially true for the raw `双持` trigger.

### B. Existing eval coverage is insufficient for this Chinese path
I inspected existing regression cases and found an English mechanics claim case involving:
- `levitate`
- `two-handed weapon in one hand`

I did **not** see a matching Chinese regression case for the Barb query in the checked eval file. That gap should be closed.

### C. End-to-end behavior should be asserted at Telegram formatting level
Since Telegram uses `_render_telegram_answer()`, at least one regression should verify the final rendered message does:

- contain the direct mechanic answer
- not contain the generic fallback
- not regress into a verbose CLI-style block unexpectedly

### D. `concise` issue can still cause renderer divergence elsewhere
Even if Telegram strips extra sections today, other surfaces or future render changes may expose the missing `concise` propagation. It is real technical debt, just not the blocker for this incident.

---

## 7) Final assessment

- **Investigation quality:** mostly correct on the immediate failure chain
- **Root cause claim:** confirmed
- **One-line fix sufficiency:** sufficient for this exact Telegram symptom, but only a partial product fix
- **Recommended decision:** revise the implementation note and test plan before treating this as fully approved

---

## 8) Reviewer recommendation

**Recommended outcome:** implement the classifier hotfix as a narrow incident fix **only if** accompanied by:

1. one explicit Chinese regression for the reported query  
2. one or more boundary tests for `双持` / `单手`+`双手` over-classification  
3. clear documentation that `concise` propagation is secondary cleanup, not the primary fix  
4. a follow-up task to review Chinese mechanics-claim detection more systematically
