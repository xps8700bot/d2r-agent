# Reddit 历史热帖回归 — 2026-03-31

## 主题
Spirit / Insight 底材、Larzuk 打孔、4 孔 ilvl breakpoint

## 热帖问题模式
- Normal cows 掉的 Crystal Sword 拿去 Larzuk 会不会出 4 孔？能不能做 Spirit？
- 哪里找适合 Larzuk 打 4 孔的 Spirit / Insight 底材？
- 为什么同样是普通底材，有的人打出来不是 4 孔？

## 正确结论
- Larzuk 给的是该物品在对应 ilvl 区间允许的最大孔数，不是“固定 4 孔”或“随机孔数”。
- 以 Crystal Sword 为例：
  - 1-25 -> 3 sockets
  - 26-40 -> 4 sockets
  - 41+ -> 6 sockets
- 所以用户真正该问的是：这个底材掉落时的 ilvl 是否落在 26-40 区间。
- 如果是，就可以通过 Larzuk 获得 4 孔，满足 Spirit 的需求；如果不是，就会打出错误孔数。

## 常见误区
- 误以为“Normal 掉的 Crystal Sword 一定能 4 孔”
- 误以为 Larzuk 打孔是随机的
- 只记符文顺序，不看底材 ilvl breakpoint

## 本次实现
- 新增 Reddit 风格回归测试：`tests/test_item_bases.py::test_reddit_hot_question_crystal_sword_larzuk_spirit_breakpoint`
- 在 orchestrator 中新增 Larzuk / socket breakpoint 推理分支
- 让回答能从 item base 结构化记录直接推出 Spirit 4 孔可行性

## 下一步候选
- Broad Sword 的 4 孔 breakpoint
- Flail -> HOTO / CTA 相关误区
- Polearm / Partizan / Thresher 的 Insight 孔数与掉落阶段
