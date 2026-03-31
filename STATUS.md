# D2R Agent — Status

Last updated: 2026-03-17 (America/Los_Angeles)

## Current state
- Repo: `workspace/d2r_agent/`
- MVP end-to-end loop is working (gap detect → retrieval router → whitelist retrieval → extract evidence → compose answer → memory gate → trace).
- Live retrieval (TheAmazonBasin) is enabled for intents: `runeword_recipe`, `cube_recipe`.
- Regression tests: **11/11 passing** (up from 3/11 baseline on 2026-03-09).

## Strategy Cards
- `data/strategy_cards.jsonl`: **176 cards** (up from 22 as of 2026-03-05)
  - Warlock Overview: 19 cards
  - Fire Warlock Leveling (S13): 42 cards
  - Abyss Warlock Leveling (S13): 32 cards
  - Summoner Warlock Endgame (S13): 40 cards
  - Echoing Strike Warlock Endgame (S13): 43 cards
- Note: maxroll.gg renders +X item mods as HTML icons; scraped as "+" or lost — literal "+skills" token is absent from cards. FCR keyword is a reliable proxy.

## Next focus (planned)
- Add more seed URLs (Paladin, Sorceress, Amazon, Druid, Necromancer builds) for broader coverage.
- Improve Chinese CJK tokenization / alias matching for queries.
- Basin runeword fact extraction script (ingest_basin_runeword_facts.py — stubs exist, not run).
- Add regression cases for strategy card retrieval across build paths.

## Notes
- There are usually **no** long-running D2R subagents; "dev progress" should be answered from this file + memory notes, not from runtime task lists.
