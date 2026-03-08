# D2R Agent — Status

Last updated: 2026-03-05 (America/Los_Angeles)

## Current state
- Repo: `workspace/d2r_agent/`
- MVP end-to-end loop is working (gap detect → retrieval router → whitelist retrieval → extract evidence → compose answer → memory gate → trace).
- Live retrieval (TheAmazonBasin) is enabled **only** for intents:
  - `runeword_recipe`
  - `cube_recipe`
- Strategy Cards pipeline is wired, but dataset is still tiny:
  - `data/strategy_cards.jsonl`: 22 lines (cards)
  - Roadmap: `notes/strategy-cards-roadmap.md`

## Next focus (planned)
- Expand Strategy Cards to ~200–500 (start with one path, then scale).
- Improve hit-rate for Chinese queries (CJK tokenization + aliases/synonyms; reduce false matches).
- Add/expand regression cases for strategy-card hits.

## Notes
- There are usually **no** long-running D2R subagents; “dev progress” should be answered from this file + memory notes, not from runtime task lists.
