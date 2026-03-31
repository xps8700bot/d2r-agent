from __future__ import annotations

from typing import Any

from d2r_agent.schemas import Answer


def followups_for_missing_fields(missing_fields: list[str], ctx: dict[str, Any] | None = None) -> list[Answer.Followup]:
    out: list[Answer.Followup] = []
    ctx = ctx or {}

    for f in missing_fields:
        # If ctx already contains a usable value, don't ask.
        if ctx.get(f, None) not in (None, "", "unknown"):
            continue

        if f == "mode":
            fu = Answer.Followup(
                id="ctx_mode",
                question="你的角色是软核(SC)还是硬核(HC)？",
                field="mode",
                allowFreeText=False,
                choices=[
                    Answer.FollowupChoice(label="软核 SC", value="SC", ctxPatch={"mode": "SC"}),
                    Answer.FollowupChoice(label="硬核 HC", value="HC", ctxPatch={"mode": "HC"}),
                ],
            )
            out.append(fu)

        elif f == "offline":
            fu = Answer.Followup(
                id="ctx_offline",
                question="你是离线(单机)还是在线(Battle.net)？",
                field="offline",
                allowFreeText=False,
                choices=[
                    Answer.FollowupChoice(label="离线/单机", value="true", ctxPatch={"offline": True}),
                    Answer.FollowupChoice(label="在线", value="false", ctxPatch={"offline": False}),
                ],
            )
            out.append(fu)

        elif f == "ladder_flag":
            fu = Answer.Followup(
                id="ctx_ladder_flag",
                question="你是天梯还是非天梯？",
                field="ladder_flag",
                allowFreeText=False,
                choices=[
                    Answer.FollowupChoice(label="天梯", value="ladder", ctxPatch={"ladder_flag": "ladder"}),
                    Answer.FollowupChoice(label="非天梯", value="non-ladder", ctxPatch={"ladder_flag": "non-ladder"}),
                    Answer.FollowupChoice(label="离线/单机(不区分天梯)", value="offline", ctxPatch={"ladder_flag": "offline", "offline": True}),
                ],
            )
            out.append(fu)

    return out


def followups_for_build_compare(*, intent: str, entities: list[str], ctx: dict[str, Any] | None = None) -> list[Answer.Followup]:
    # Requirement: Insight vs Spirit => ask who.
    if intent != "build_compare":
        return []

    if not any(e in entities for e in ["眼光", "精神", "Insight", "Spirit"]):
        return []

    ctx = ctx or {}
    # If user already answered, do not ask again.
    if ctx.get("who") not in (None, "", "unknown"):
        return []

    fu = Answer.Followup(
        id="who",
        question="你是打算给自己用，还是给第二幕佣兵(米山)用？",
        field="who",
        allowFreeText=False,
        choices=[
            Answer.FollowupChoice(label="给自己用", value="self", ctxPatch={"who": "self"}),
            Answer.FollowupChoice(label="给米山用", value="merc", ctxPatch={"who": "merc"}),
            Answer.FollowupChoice(label="不确定", value="unknown", ctxPatch={"who": "unknown"}),
        ],
    )
    return [fu]


def followups_for_runeword_recipe(*, intent: str, entities: list[str], ctx: dict[str, Any] | None = None) -> list[Answer.Followup]:
    # Minimal: if user asks about Spirit, we can ask about the base (socket count / white-gray).
    if intent != "runeword_recipe":
        return []
    if not any(e in entities for e in ["精神", "Spirit"]):
        return []

    ctx = ctx or {}
    if ctx.get("base_4os") not in (None, "", "unknown"):
        return []

    fu = Answer.Followup(
        id="base_4os",
        question="你的君主盾（鸢盾）现在是 4 孔的白/灰底材吗？（符文之语必须白/灰，Spirit 盾需要 4 孔）",
        field="base_4os",
        allowFreeText=False,
        choices=[
            Answer.FollowupChoice(label="是，4孔白/灰", value="true", ctxPatch={"base_4os": True}),
            Answer.FollowupChoice(label="不是/不确定", value="false", ctxPatch={"base_4os": False}),
        ],
    )
    return [fu]


def followups_for_mechanics(*, intent: str, ctx: dict[str, Any] | None = None) -> list[Answer.Followup]:
    ctx = ctx or {}
    out: list[Answer.Followup] = []

    if intent in {"affix_level_rule"}:
        if ctx.get("ilvl") in (None, "", "unknown"):
            out.append(
                Answer.Followup(
                    id="ilvl",
                    question="这个物品的 ilvl 是多少？（如果不确定，请告诉我掉落来源：怪物/区域/是否 Baal GC）",
                    field="ilvl",
                    allowFreeText=True,
                    choices=[Answer.FollowupChoice(label="不确定/先跳过", value="unknown", ctxPatch={"ilvl": "unknown"})],
                )
            )
        if ctx.get("base_item") in (None, "", "unknown"):
            out.append(
                Answer.Followup(
                    id="base_item",
                    question="底材是什么？（例如：amulet / ring / grand charm / monarch 等）",
                    field="base_item",
                    allowFreeText=True,
                    choices=[Answer.FollowupChoice(label="amulet(项链)", value="amulet", ctxPatch={"base_item": "amulet"}),
                             Answer.FollowupChoice(label="grand charm(GC)", value="grand_charm", ctxPatch={"base_item": "grand_charm"}),
                             Answer.FollowupChoice(label="不确定", value="unknown", ctxPatch={"base_item": "unknown"})],
                )
            )
        if ctx.get("affix") in (None, "", "unknown"):
            out.append(
                Answer.Followup(
                    id="affix",
                    question="你要判断的是哪个 affix？（给我英文名或中文描述都行）",
                    field="affix",
                    allowFreeText=True,
                    choices=[Answer.FollowupChoice(label="不确定/先讲规则", value="unknown", ctxPatch={"affix": "unknown"})],
                )
            )

    return out


def build_followups(*, missing_fields: list[str], intent: str, entities: list[str], ctx: dict[str, Any] | None = None) -> list[Answer.Followup]:
    out: list[Answer.Followup] = []
    out.extend(followups_for_missing_fields(missing_fields, ctx=ctx))
    out.extend(followups_for_build_compare(intent=intent, entities=entities, ctx=ctx))
    out.extend(followups_for_runeword_recipe(intent=intent, entities=entities, ctx=ctx))
    out.extend(followups_for_mechanics(intent=intent, ctx=ctx))

    # De-dupe by id (keep first).
    seen: set[str] = set()
    deduped: list[Answer.Followup] = []
    for fu in out:
        if fu.id in seen:
            continue
        seen.add(fu.id)
        deduped.append(fu)

    return deduped
