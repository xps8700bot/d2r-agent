# Strategy Cards Roadmap（从术士 Warlock 起步）

> 目标：先把「单一路径」做成**可持续生产、可检索命中、可追溯引用、可回归验证**的闭环；再按同一套模板扩展到多流派、多职业。

## 0. 背景与现状（2026-03-01）

### 现状
- Strategy Cards 存储：`d2r_agent/data/strategy_cards.jsonl`
- 当前覆盖：**Warlock / 术士**（来自 Maxroll）为主，总计约 20+ 条（MVP 数据量很小，刻意从一条路径开始）。
- 当前检索：`knowledge/strategy_cards.py` 采用**朴素 token 子串匹配**（非 embedding）。
  - token 规则：仅保留长度 ≥ 3 的 token（对中文两字流派名命中不友好）
  - 计分规则：token 出现在 topic/nugget/tags/title_path 中则加分
- 使用点：`orchestrator.py` 在 intent 属于 `build_advice`/`build_compare` 时会优先尝试命中策略卡并把 nugget 放到 TL;DR。

### 为什么先从术士开始
- 降低变量：先验证 **采集 → 清洗 → 命中 → 输出** 全链路是否稳定
- 快速形成“样板”：写清楚卡片结构、命中策略、质量门槛与回归用例
- 便于扩展：后续只需要复制模板，换数据源与别名表即可扩展

---

## 1. Strategy Card 的定义（契约）

每条卡片是一个 JSONL 记录（每行一个 JSON），推荐字段：
- `topic`：主题（如 `Warlock Overview`）
- `tags`：来源/类别/职业/流派标签（如 `maxroll`, `strategy`, `warlock`, `leveling`）
- `nugget`：一条可执行策略（短、具体、可操作；尽量避免硬数值）
- `source_site` / `source_url`：可追溯来源
- `title_path`：来源页面的章节路径（便于定位上下文）
- `created_at`：生成时间

**质量门槛（必须满足）：**
1) `nugget` 必须能独立执行（不是空泛观点）
2) `source_url` 必须在白名单域（至少当前阶段为 Maxroll/TheAmazonBasin 等允许域）
3) 尽量避免硬数值断言；若必须出现数值，需明确其上下文/条件（避免误导）

---

## 2. 当前已打通的“术士路径”闭环

### 2.1 数据采集
- 脚本：`d2r_agent/scripts/ingest_strategy_maxroll.py`
- 产物：`d2r_agent/data/strategy_cards.jsonl`

### 2.2 运行时命中
- 入口：`d2r_agent/src/d2r_agent/orchestrator.py`
- 命中函数：`d2r_agent/src/d2r_agent/knowledge/strategy_cards.py::search_strategy_cards`
- 输出位置：Answer 的 TL;DR 前几条，格式：
  - `[Strategy] {nugget} (source: {url})`

### 2.3 可追溯
- 每次回答都会写 trace：`d2r_agent/traces/...json`
- trace 中包含 `strategy_hits`（topic/source_url/title_path），用于复盘“为什么命中/没命中”。

---

## 3. 近期计划（把 Warlock 做扎实）

### 用户确认的优先顺序（样板路径）
- **A → C → B**
  - A) Leveling（1–75）
  - C) Gearing / 属性优先级（通用、耐久）
  - B) Endgame（最后做，避免早期就陷入高变量/版本差异）

### P0（本周优先）
1) **扩充 Warlock 数据量（按 A→C→B）**
   - 目标：从 ~20 条 → 200–500 条
   - 方式：少量页面、深度提纯；对每页建立“允许抽取章节白名单”，宁缺毋滥。
   - 交付物：维护一个“页面清单 + 章节白名单”清单文件（见下方 `notes/warlock-strategy-sources.yaml`）。
2) **提升命中率：加入别名/同义词层（轻量且可控）**
   - 例如：`warlock` ↔ `术士`
   - 优先在 ingest 阶段给 tags 增加中文别名；避免 runtime 过度扩展导致误命中。
3) **回归用例增加 Warlock 专用 case**
   - `eval/regression_cases.yaml`：增加 10 条起步（覆盖 leveling / gearing / endgame），断言必须出现 `[Strategy]` 或关键 token。

### P0-A：Warlock Leveling（样板先行，慢但干净）
- 来源清单：`notes/warlock-strategy-sources.yaml`
- 用户选择：**Summoner（召唤术士）** 优先作为样板路径
  - 备注：Maxroll 的 Summoner 页面是 Endgame Guide，但其「Skills / Gameplay」包含可用于 1–75 的技能加点顺序与早期操作要点。
- 目标：先把 Leveling 相关页面做成“干净样板”，产出 80–150 条高质量 nugget，再扩到 200–500。
- 抽取策略：只从 `allowed_sections` 中抽取；其余一律忽略（宁缺毋滥）。

### P1（下周）
1) **改进 token 规则（兼容中文两字）**
   - 方案：将 token 长度阈值从 3 降到 2，但配合停用词表防噪
   - 或：仅对 CJK token 允许长度 2
2) **去噪与去重复**
   - ingest 端对相似 nugget 做合并（同段落重复抽取/截断问题）
3) **卡片格式稳定化**
   - 写一个 JSON schema 校验脚本（CI 可选）

---

## 4. 扩展计划（多路径 → 多职业）

> 原则：每扩一个职业/流派，都要复制同一套“闭环”与“质量门槛”。

### 扩展顺序（建议）
1) **Warlock（完成）** → 2) Sorceress（冰法/电法） → 3) Paladin（锤丁/盾击） → 4) Barbarian（旋风） → …

### 每个新职业的交付清单（Definition of Done）
- [ ] 至少 200 条 strategy cards
- [ ] alias/标签覆盖（中英文名、常见流派缩写）
- [ ] 10+ 条回归用例
- [ ] 在 20 条手工测试 query 下，命中率 ≥ 60%（可先粗略统计）
- [ ] 误命中（明显不相关）≤ 10%

---

## 5. 维护与更新方式（长期）

### 什么时候更新
- 每次完成：
  - 新增采集源 / 新职业 / 命中逻辑改动 / 质量门槛调整
- 每次出现“没命中”用户反馈：
  - 记录 query → 看 trace.strategy_hits（为空则进入改进清单）

### 怎么记录
- 只改这一个文档：`notes/strategy-cards-roadmap.md`
- 用“变更记录”追加一行：日期 + 做了什么 + 结果（命中率/样本数）

---

## 6. 变更记录

- 2026-03-01：建立文档；确认先以 Warlock 打通单一路径，再按模板扩展到多职业。
