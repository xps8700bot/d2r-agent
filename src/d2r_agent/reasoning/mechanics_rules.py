from __future__ import annotations

from dataclasses import dataclass, field

from d2r_agent.knowledge.mechanics_db import MechanicsHit


@dataclass
class MechanicsReasoningResult:
    answer: str
    why: list[str] = field(default_factory=list)
    formula: str | None = None
    conditions: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    formulas_used: list[str] = field(default_factory=list)
    missing_inputs: list[str] = field(default_factory=list)
    rules_applied: list[str] = field(default_factory=list)


def explain_magic_find_base_item(*, hits: list[MechanicsHit]) -> MechanicsReasoningResult:
    # Minimal rule: MF affects quality selection, not base item / TC selection.
    rid = "mf.quality_only.v1"
    return MechanicsReasoningResult(
        answer="不会。MF（Magic Find）影响的是物品‘品质/质量’（unique/set/rare/magic）的选择概率，通常不改变 TC/底材（base item）的选择。",
        why=[
            "掉落流程里一般先由 Treasure Class/掉落条目决定‘会掉什么底材/类别’，然后才在该底材上做‘品质（unique/set/rare/magic）’的判定。",
            "因此 MF 主要改变‘同一底材’变成更高品质的概率，而不是让‘更高级底材’出现得更多。",
        ],
        rules_applied=[rid],
        evidence_ids=[h.record.id for h in hits[:2]],
    )


def explain_tc_order(*, hits: list[MechanicsHit]) -> MechanicsReasoningResult:
    rid = "tc.order.v1"
    return MechanicsReasoningResult(
        answer="通常是先走 TC/掉落条目（决定底材/类别），再做品质（unique/set/rare/magic）判定。",
        why=[
            "TC（Treasure Class）用于描述‘从哪些条目里抽取掉落’（可理解为候选池/表）。",
            "抽到具体条目后，才在该条目（底材/物品类型）上进行品质与其它生成步骤。",
        ],
        rules_applied=[rid],
        evidence_ids=[h.record.id for h in hits[:2]],
    )


def explain_craft_amulet_93(*, hits: list[MechanicsHit]) -> MechanicsReasoningResult:
    # Minimal: show craft ilvl formula and why 93 is used.
    fid = "craft.amulet.ilvl.v1"
    formula = "crafted_ilvl = floor(0.5 * clvl) + floor(0.5 * ilvl)"
    return MechanicsReasoningResult(
        answer="常说 93 级，是为了让手工项链（crafted amulet）的最终 ilvl 足够高，从而有机会滚到最高需求的 +2 全技能词缀（需要较高 alvl）。",
        why=[
            "手工品的 ilvl 由角色等级(clvl)和底材 ilvl 共同决定（见公式）。",
            "当 clvl 提升时，crafted_ilvl 的下限随之抬高，能解锁更高 alvl 的 affix 池。",
            "93 是社区常用的‘够用阈值’，能让多数来源的护身符在计算后达到用于 +2 词缀的要求区间。",
        ],
        formula=formula,
        rules_applied=[fid],
        formulas_used=[fid],
        evidence_ids=[h.record.id for h in hits[:2]] or [fid],
    )


def explain_baal_gc_45_life(*, hits: list[MechanicsHit]) -> MechanicsReasoningResult:
    rid = "charm.gc.45life.v1"
    return MechanicsReasoningResult(
        answer="因为 Baal（以及 Diablo / Nihlathak）来源的 GC ilvl 很高，推到足够的 alvl 后，就能解锁 ‘of Vita’ 这类高阶生命后缀（最高 45 life）。",
        why=[
            "GC 能不能出 45 life 本质是‘该后缀是否在 affix 池里可用’，这由 alvl 决定。",
            "而 alvl 又由 ilvl 与底材 qlvl 的规则推导出来；Baal GC 的 ilvl 属于最高档，因此满足该后缀的门槛。",
        ],
        formula="(high ilvl) -> high alvl -> allows Vita(41-45 life) suffix",
        conditions=["必须是足够高 ilvl 的 GC（常见说法：Baal/Diablo/Nihl GC）"],
        rules_applied=[rid],
        formulas_used=[rid],
        evidence_ids=[h.record.id for h in hits[:2]] or [rid],
    )


def affix_possible_or_need_inputs(*, hits: list[MechanicsHit], ctx: dict) -> MechanicsReasoningResult:
    missing = []
    for f in ["ilvl", "base_item", "affix"]:
        if ctx.get(f) in (None, "", "unknown"):
            missing.append(f)
    if missing:
        return MechanicsReasoningResult(
            answer="需要更多输入才能判断。",
            why=["affix 是否可能出现取决于 ilvl/qlvl/alvl 与具体 affix 的等级需求（alvl）。"],
            missing_inputs=missing,
            rules_applied=["affix.alvl.rule.v1"],
            evidence_ids=[h.record.id for h in hits[:2]],
        )

    return MechanicsReasoningResult(
        answer="我可以据此计算并判断该 affix 是否可能出现（此处 MVP 先走变量收集与公式引用）。",
        why=["已获得必要变量；下一步按 alvl 规则计算并匹配 affix 等级需求。"],
        rules_applied=["affix.alvl.rule.v1"],
        evidence_ids=[h.record.id for h in hits[:2]],
    )
