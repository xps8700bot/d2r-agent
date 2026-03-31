# d2r_agent intent classifier v2 plan (2026-03-28)

## Goal
Replace the current brittle rule-only routing with a complete v2 design:
- deterministic rules for high-signal intents
- LLM fallback for rule misses / `general`
- strict structured output schema for fallback classification
- traceability for intent source
- regression coverage for both routing and user-visible Telegram behavior

## Product requirements
1. If default information is sufficient, answer directly and fully.
2. Do not ask low-value follow-up questions.
3. Do not leave “hook” lines inviting more questions when the answer is already complete.
4. Strong-fact questions may still use retrieval and cross-validation.
5. Intent routing must be inspectable and testable.

## v2 routing model
### Stage 1: rule classifier
Rules continue to own these high-signal intents:
- runeword_recipe
- cube_recipe
- season_info
- patch_change
- drop_rate
- build_compare
- build_advice
- magic_find_rule
- treasure_class_rule
- affix_level_rule
- charm_rule
- crafting_rule

### Stage 2: LLM fallback classifier
Triggered only when the rule classifier returns:
- `general`
- or an explicitly marked low-confidence rule result (optional future extension)

Primary fallback targets:
- mechanics_claim
- mechanics_query
- residual build/general ambiguity

## Fallback output schema
The LLM classifier must return a constrained JSON object:

```json
{
  "intent": "mechanics_claim",
  "confidence": "high",
  "reason_code": "weapon_interaction_rule",
  "needs_review": false
}
```

### Allowed intents
- runeword_recipe
- magic_find_rule
- treasure_class_rule
- affix_level_rule
- charm_rule
- crafting_rule
- cube_recipe
- drop_rate
- build_compare
- build_advice
- patch_change
- mechanics_claim
- season_info
- mechanics_query
- general

### Allowed confidence values
- high
- med
- low

### Allowed reason_code values
Keep a small enum such as:
- weapon_interaction_rule
- mechanic_capability_question
- boss_farming_question
- gear_tradeoff
- recipe_query
- season_timing
- unknown

## Decision policy
- Strong rule hit -> accept rule result, no LLM call.
- Rule result == general -> invoke LLM fallback.
- If fallback returns non-general with confidence high/med -> accept fallback result.
- If fallback returns low confidence -> keep general.

## Traceability requirements
Trace / logs must record:
- rule_intent
- final_intent
- intent_source (rule | llm_fallback)
- fallback_confidence
- fallback_reason_code

## Behavior requirements for direct-answer queries
For direct-answer mechanics claims (example: Barb one-handing a two-handed weapon):
- no low-value follow-up
- no generic fallback language
- no “if you want, I can continue” hook
- answer should include conclusion + why + boundary conditions + how it works in practice

## Implementation scope
Complete implementation includes:
1. refactor rule classifier into an explicit rule-stage function
2. add fallback schema and LLM classification helper
3. integrate final intent resolution into context-gap path
4. ensure retrieval router and answer composer use final intent
5. record intent source in trace/events
6. update Telegram rendering to suppress hook language for complete answers
7. add regression tests for routing + user-visible behavior

## Regression set (minimum)
### Rule-stable
- 谜团怎么做 -> runeword_recipe
- Spirit 盾符文顺序 -> runeword_recipe
- 这个赛季什么时候开始 -> season_info
- 天梯禁用了没有 -> season_info
- 精神还是眼光 -> build_compare
- 冰法还是火法开荒 -> build_compare
- 女伯爵掉 Lo 吗 -> drop_rate

### Fallback-targeted
- 野蛮人怎么单手那双手武器 -> mechanics_claim
- 死灵能不能 levitate -> mechanics_claim

### Anti-regression
- 双持旋风蛮开荒怎么配 -> build_advice/build_compare, not mechanics_claim by default
- 双手剑开荒选哪把 -> build_advice
- 野蛮人双持开荒 -> build_advice

### Telegram behavior
For direct-answer mechanics claims:
- no follow-up hook
- no generic fallback line
- direct complete answer present

## Review requirement
After implementation, run a dedicated review pass before any push.
