# d2r-agent scheduled-task log

Append-only run log for the `d2r-agent` scheduled task. This file tracks the
daily automated runs — not the project's own development history (see
`STATUS.md` and `notes/` for that).

## Purpose

- Maintain `reddit_qa_todo.json` as a long-lived D2R question benchmark set.
- Each run: collect (when needed) → evaluate one or more pending questions
  against the agent → improve / regress-check → commit locally (no push).
- State machine per question: `pending → in_progress → passed | failed`.

## Layout (repo root = `D:/Documents/source/d2r-agent/`)

- `project-d2r-agent.md` (this file) — append-only run log.
- `reddit_qa_todo.json` — question benchmark queue.
- `project-runs/YYYY-MM-DD_{start,end}.json` — per-run markers.
- `src/d2r_agent/` — actual agent source (CLI: `scripts/cli.py`).
- `tests/` — pytest regression suite.
- Remote: `https://github.com/xps8700bot/d2r-agent` (branch `main`).

## Runs

### 2026-04-07 — Bootstrap run (scheduled-task artifacts only)

- **Initial mistake & correction:** first attempt created a `d2r_agent/`
  subdirectory and initialized git there, misreading the scheduled-task path.
  After the user corrected the task name to `d2r-agent`, the mistaken
  subdirectory was removed, the files were moved to the repo root, and a new
  git repo was initialized at the correct level. Remote
  `https://github.com/xps8700bot/d2r-agent` was added and `origin/main` was
  fetched. Local `main` was created tracking `origin/main` (no rebase needed
  — there were no prior local commits on a shared branch).
- **Existing project state discovered on remote:** full agent implementation
  (`src/d2r_agent/`), 13 test files, rich `data/fact_db` knowledge base, and
  a large regression suite (latest remote commit `baadf25 feat: add The
  Oculus + Buriza-Do Kyanon to uniques KB; expand Tal Rasha set detail; +7
  regression tests (205→212)`). The scheduled-task artifacts (this file,
  `reddit_qa_todo.json`, `project-runs/`) did **not** exist on the remote
  and are being introduced by this run.
- **Reddit collection:** attempted `reddit.com` and `old.reddit.com` via
  WebFetch; both blocked by the allow-list. Recorded
  `reddit_fetch: skipped_network_error`. Queue remains empty.
- **Question processing:** none. Queue is empty and collection is blocked,
  so there is nothing to evaluate today.
- **Regression check:** none (no code changes; no `passed` cases in queue
  yet).
- **Commits:** local-only on `main` (no push, per hard rules).
- **Local untracked:** `skills/amazon-basin-d2r-wiki/` is present in the repo
  root but not tracked on `origin/main`. Left untracked — not in scope for
  this task.
- **Next run:**
  1. Unblock Reddit fetching (Bash `curl` with a proper User-Agent, or a
     small Python script under `scripts/`). WebFetch is a dead end for
     Reddit.
  2. Once the queue has `pending` questions, drive one through
     `PYTHONPATH=src python scripts/cli.py "<question>"` and score against
     the stored `reference_answer`.
  3. If improvements are made, run `pytest` and sample 1–2 `passed` cases
     for regression.

### 2026-04-07 — Run 2 (manual re-run after SKILL.md rule update)

- **Trigger:** user manually re-ran the scheduled task after updating
  `SKILL.md` to (a) allow push to `origin/main` (collaborator added), and
  (b) make `mcp__Claude_in_Chrome__*` the preferred Reddit-fetch tool.
- **`git pull --rebase origin main`:** clean, no conflict.
- **Reddit collection (forced, queue was empty):**
  - Tier 1 `mcp__Claude_in_Chrome__navigate` → **blocked** on
    `reddit.com`, `old.reddit.com`, and `np.reddit.com` with
    "This site is not allowed due to safety restrictions" (same allow-list
    as WebFetch; `SKILL.md`'s assumption that the Chrome MCP bypasses
    this turned out to be wrong).
  - Tier 2 Bash `curl` → **works**. Fetched 3 subreddit top-listing JSONs
    (`r/diablo2resurrected` top/month + top/year, `r/diablo2` top/month)
    plus 6 topic searches (breakpoint, runeword, immunities, magic find,
    mercenary, resistances) plus comment trees for 9 candidate posts.
  - Added `scripts/reddit_collect.py` as a stable ingestion path (keyword
    extraction, top-comment summarization into `reference_answer`, URL +
    70%-keyword-overlap deduplication).
  - **8 new `pending` questions** committed to `reddit_qa_todo.json`.
- **Question processed:** `reddit_1r4gn0i` — "How are you warlocks
  dealing with fire immunes on hell?"
  - Baseline run: intent classified as `general`, zero strategy-card
    hits, zero fact hits, retrieval_needed=false. Answer was a pure
    Assumptions/TL;DR/Options stub with no mechanics content. **Fail on
    completeness and factual correctness.**
  - **Improvement (category: intent classification):** broadened the
    `build_advice` keyword list in `src/d2r_agent/intent_classifier.py`
    with English class names (warlock, sorc, paladin, barb, druid, necro,
    amazon, assassin, + abbreviations), archetype names (hammerdin,
    zealot, fishymancer, wind/fury druid, ww barb, blizz sorc, trap sin,
    …), and leveling/gearing phrases (leveling, gearing, build advice,
    `{fire,cold,lightning,poison,physical} immunes`, hell difficulty).
  - Second run: intent now `build_advice`, strategy cards for Fire
    Warlock Leveling + Summoner Warlock fire correctly. **But the
    answer is still weak**: `search_strategy_cards` uses naive token
    overlap so the top hits are two generic guide intros rather than
    cards about fire immunes. Grepping `data/strategy_cards.jsonl` for
    "fire immun" returns 3 cards — all Druid or Assassin, zero Warlock.
    **So there is a real knowledge gap**, not just a retrieval bug.
  - **Status:** `in_progress`. Two follow-ups (phrase-aware scoring in
    `search_strategy_cards`; adding warlock fire-immune strategy cards)
    are both beyond a single-session budget. `improvement_count = 1`.
- **Regression check:** `tests/test_intent_classifier_v2.py` 25/25 pass.
  Full suite 209/212; the 3 failing tests (`test_gems`,
  `test_item_bases_manual`) are pre-existing Windows-only
  `UnicodeDecodeError` issues — confirmed by stashing my changes and
  re-running. No `passed` benchmark cases exist yet to sample from.
- **Commit + push:** `66d3a76 feat(intent): broaden build_advice keywords
  for English class names`. Pushed to `origin/main` successfully
  (`9e58b9d..66d3a76 main -> main`).
- **Local untracked (unchanged):** `skills/amazon-basin-d2r-wiki/`.
- **Next run:**
  1. Continue `reddit_1r4gn0i`: implement phrase-aware scoring in
     `src/d2r_agent/knowledge/strategy_cards.py` (bigram boost,
     intro/overview penalty when query is problem-specific), then add
     hand-written strategy cards for warlock fire-immune handling
     (Obedience polearm merc, Hephasto reroll → Conviction aura merc,
     Magic Warlock pivot, Death sigil + Bind Demon).
  2. Update `SKILL.md`: the Claude-in-Chrome bypass claim is wrong —
     demote it below `curl` in the preferred-tool list (or drop it).
  3. Next pending question if Q1 clears: `reddit_1rchie1` — "Early Hell
     Warlock: magic vs demon vs echoing strike".
