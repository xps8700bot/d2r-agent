# D2R Agent — TODO（结构化事实库优先）

## 目标
把“确定性硬事实”（底材/孔数/等级需求/职业可装备性/可否单手持双手等）从 LLM 流程中剥离出来，改为**程序化判断 + 可追溯证据**。

## P0 — 本地结构化事实库（本周先做）
1) 设计数据结构：`data/fact_db/runewords.json`（或 jsonl）
   - 字段建议：
     - `id` / `name_en` / `name_zh` / `aliases`
     - `variants`: [{`item_type`, `sockets`, `required_level`(可空), `rune_order`(可空)}]
     - `sources`: [{`site`, `url`, `title_path`, `extracted_at`, `snippet`(可选)}]
     - `last_verified_at`

2) 写 Basin 抽取脚本（小样本先跑，用户验收后再扩容）
   - 新增：`scripts/ingest_basin_runeword_facts.py`
   - 输入：runeword 名（例如 Insight/Spirit）
   - 输出：结构化 JSON（样本文件）
   - 抽取规则：从 Basin 页 HTML 的表格行解析：
     - `Item type`
     - `Sockets`
     - `min RLvl`（Basin 的最低需求等级字段）
     - `Rune order and modifiers`
     - `Rune Word modifiers`（需结构化数值化；stat 命名用 `fhr/fcr/frw/...`）

3) 速率限制/防 ban
   - 使用现有缓存：`d2r_agent/cache/`（已经按 URL hash 缓存）
   - 抽取脚本增加节流：默认 `--sleep 1.2`（每个页面 fetch 之间）
   - 最大抓取量分批：先 2 个（Insight/Spirit）→ 用户确认样本 → 再扩到全量

## P1 — Validator（程序化硬事实判断）
4) 新增 `facts/validator.py`
   - 输入：`class/build/level` + runeword facts
   - 输出：每个方案是否可做/可用、缺口（比如等级不够/底材不匹配）

5) Orchestrator 集成
   - 在 `answer_compose` 前：先跑 validator，生成 `FactCheck` 段落（确定性输出）
   - LLM 只负责“基于已验证事实的取舍”

## P2 — Evidence 质量提升
6) 官方链接直达抽取后，禁止再用搜索结果污染 Evidence（direct-url 优先级更高）
7) 对 Basin 搜索结果做相关性过滤（避免 WoW Warlock/Blizzard 技能等误入）

## P3 — Context 结构化
8) 扩展 `UserContext` schema：加入 `class_name/build/level/difficulty/act`（现在这些 ctx 不进核心结构）
9) build_compare 的 next_step 模板按上下文改写（别再固定问“米山”）
