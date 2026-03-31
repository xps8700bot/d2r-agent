# D2R Agent (OpenClaw) — MVP

工程文档（随时更新）：
- 当前进度：`STATUS.md`
- Strategy Cards 路线图：`notes/strategy-cards-roadmap.md`

目标：构建一个 **事实优先、可检索、可记忆、可追溯** 的 D2R（Diablo II Resurrected）问答 Agent。

本仓库目前落地 **阶段 A：MVP 闭环** + **阶段 B（initial）：TheAmazonBasin MediaWiki 实检索（部分意图）**：
- 输入问题 → Context Gap Detector → Retrieval Router → 检索（Basin: api.php + rest.php/v1；其余站点先 stub）→ Extract/Normalize → Answer Composer → Memory Gate → Memory Store → Trace log

> 注意：MVP 默认 **不凭空编造强事实数值**。强事实在未检索到证据时，会明确提示“不确定/需要检索”。

---

## 1) 安装与运行

```bash
cd d2r_agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 让 Python 能找到 src/ 下的包（二选一）：
# A) 临时（推荐做 demo）
export PYTHONPATH=src
# B) 安装为可编辑包
# pip install -e .

# 方式 1：直接运行 CLI
PYTHONPATH=src python scripts/cli.py "谜团(Enigma)符文之语怎么做？是不是天梯限定？"

# 交互式（会提示补充上下文/追问，并把 session 保存到 cache/session_state.json）
PYTHONPATH=src python scripts/cli.py "精神 还是 眼光？" --interactive

# 你可以在下一次调用里只输入一个短答案（例如 "B" / "给自己用"），它会从上一次 session 继续
PYTHONPATH=src python scripts/cli.py "给自己用" --interactive

# 带可选上下文（release_track/season_id/platform 等）
PYTHONPATH=src python scripts/cli.py "这个赛季天梯什么时候开始？" --ctx '{"release_track":"d2r_roitw","season_id":"current","platform":"PC"}'

# 方式 2：用模块方式（等价，需要 PYTHONPATH 或已 pip install -e .）
PYTHONPATH=src python -m d2r_agent.scripts.cli "悔恨(Grief)的符文顺序是什么？"
```

输出会固定包含：
- Assumptions
- TL;DR
- Evidence（MVP 可能为空或 stub）
- Options
- Next step

同时会写入 trace：
- `traces/{timestamp}_{hash}.json`（包含 current_date）
- memory：`data/memory.jsonl`
- SeasonCalendar：`data/season_calendar.json`（仅在官方证据+可解析日期时写入）

---

## 2) 白名单配置（阶段 B：Basin 优先 + 仅白名单访问）

白名单在：`src/d2r_agent/config.py` 的 `WHITELIST_DOMAINS` / `OFFICIAL_WHITELIST_DOMAINS`。

阶段 B（initial）默认包含：
- `theamazonbasin.com`（MediaWiki：已接入 `api.php` 搜索 + `rest.php/v1` 拉取 HTML 并抽取 Evidence）
- `maxroll.gg` / `diablo2.io` / `diablo2.wiki.fextralife.com`（暂时仍生成站内检索入口 URL；后续可逐站点加 adapter）

官方来源（用于赛季/机制/版本治理类强事实，优先级最高）：
- `news.blizzard.com`（官方新闻/公告/赛季宣布/补丁说明；已接入 H2/H3/H4 分段抽取）
- `us.forums.blizzard.com`（官方论坛；当前仅支持已知 thread URL 的抓取+关键词窗口抽取）

> 约束：检索层只能返回白名单域名 URL。

### 官方来源策略（Official sources policy）

- **赛季信息/天梯启用禁用/官方公告**：优先使用 `news.blizzard.com` 证据；论坛作为兜底。
- **机制硬规则（mechanics_claim）**：只有在证据来自 **官方白名单**（news/forums）时，才允许写入长期记忆；
  Basin 仅在片段内包含可追溯引用标记（链接/Ref）时才允许写入（避免把二手/口口相传写进记忆）。

---

## 3) 如何添加回归用例（阶段 D 接口先放好）

编辑：`src/d2r_agent/eval/regression_cases.yaml`

格式（MVP 先支持最简断言：必须包含某些字段/关键词）：

```yaml
- id: runeword_enigma
  query: "谜团符文之语怎么做"
  must_contain:
    - "Assumptions"
    - "Evidence"
    - "Next step"
```

运行（MVP runner）：

```bash
python src/d2r_agent/runner.py
```

---

## 4) 5 个 demo 问题（阶段 A/B 验收用）

1. `"谜团(Enigma)符文之语怎么做？是不是天梯限定？"`
2. `"D2R 2.7 以后 旋风蛮子还强吗？（给个配装思路）"`
3. `"地狱牛关掉什么符文概率最高？"`
4. `"手工项链（caster amulet）公式是什么？"`
5. `"刚回坑，单机SC，预算低，想玩冰法快速刷安姐，怎么配？"`

你会看到：
- 系统最多追问 1–3 个关键字段（MVP 中也会给出默认假设并继续）
- 强事实类问题会被路由到检索
  - `runeword_recipe` / `cube_recipe`：**会对 TheAmazonBasin 做真实检索并抽取 EvidenceSnippet**
  - 其他强事实：暂时仍只生成检索入口（避免抓取面过大）
- trace 中记录 intent、缺口字段、检索计划、证据片段、是否写入记忆

---

## 5) 阶段 B（initial）已接入的真实检索 & 配置旋钮

### 已接入
- TheAmazonBasin（MediaWiki）
  - 搜索：`https://www.theamazonbasin.com/w/api.php?action=query&list=search...`
  - 页面 HTML：`https://www.theamazonbasin.com/w/rest.php/v1/page/{title}/html`
  - 抽取：`retrieval/extract.py`（目前仍是“粗抽取”，优先段落/列表；后续可加强表格/标题层级）
  - 缓存：`CACHE_DIR` 下按 URL hash 缓存（search JSON 与 page HTML 都会缓存）

### 当前仅对哪些 intent 做 live retrieval？
在 `orchestrator.py` 里，暂时仅对以下强事实意图执行真实检索（其余强事实仍给入口，避免抓取面过大）：
- `runeword_recipe`
- `cube_recipe`

### 配置旋钮（代码常量）
在 `src/d2r_agent/config.py`：
- `WHITELIST_DOMAINS`：允许访问的域名（已包含 `theamazonbasin.com`）
- `HTTP_TIMEOUT_S` / `HTTP_MAX_RETRIES`：HTTP 超时与重试
- `CACHE_DIR`：缓存目录

---

## 6) 快速 demo（能看到真实 EvidenceSnippet）

```bash
PYTHONPATH=src python scripts/cli.py "谜团(Enigma)符文之语怎么做？"
```

期望现象：
- Evidence 里会出现 `theamazonbasin.com | https://www.theamazonbasin.com/wiki/... | <snippet>`
- trace 里 `sources_used` 会包含 basin 的 /wiki URL

---

## 7) Telegram inline-button 风格 follow-ups（供 OpenClaw 主 Agent 调用）

### Answer schema 新增 followups
`Answer.followups` 是可选字段，每个 followup 包含：
- `id`, `question`, `field`
- `choices`: `{label,value,ctxPatch}`
- `allowFreeText`: true 时 choices 会包含 `其他/手动输入`（value=`__free_text__`）

当前会在两类场景生成：
1) `missing_fields` 包含 `mode/offline/ladder_flag`：给固定选项 + 手动输入
2) `build_compare` 且实体包含 Insight/Spirit（眼光/精神）：生成 `who`（给自己/给米山/不确定/其他）

### CLI：--json 输出（机器可读）

```bash
PYTHONPATH=src python scripts/cli.py "精神 还是 眼光？" --json
```

输出 JSON 形如：
- `text`: 传统人类可读文本
- `trace_path`
- `answer`: 结构化 Answer（包含 `followups`）

### Telegram callback_data 编码

见 `d2r_agent/telegram_followups.py`：
- `encode_ctx_patch(ctxPatch)` → `d2r:ctx:{base64url-json}`
- `followups_to_inline_keyboard(followups)` → `{"inline_keyboard": ...}`

### Telegram session-state（按 chat_id 记忆并重跑）

见 `d2r_agent/telegram_session_state.py`：
- `upsert_session(state_path, chat_id, last_user_query, ctx)`：首次用户问题后写入
- `apply_patch_and_rerun(state_path, chat_id, ctx_patch)`：用户点击按钮后，应用 ctxPatch 并重跑原 query

### OpenClaw 主 Agent 伪代码示例

1) 用户发来 query：
- 调 `answer(query, ctx)` 得到文本 + trace_path
- 从 trace 的 `events[].step==answer_compose` 取出 `followups`
- `upsert_session(..., chat_id, last_user_query=query, ctx=ctx)`
- 用 `followups_to_inline_keyboard()` 生成 inline keyboard 并发送

2) 用户点击按钮（收到 callback_data）：
- `ctx_patch = decode_ctx_patch(callback_data)`
- `out, trace_path, _ = apply_patch_and_rerun(state_path, chat_id, ctx_patch)`
- 再次从 trace 取 `followups`，继续发按钮（如果还有）
