"""Tests for uniques.jsonl and sets.jsonl mechanics_db entries."""
import os
import pytest
from d2r_agent.knowledge.mechanics_db import search_mechanics

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNIQUES_PATH = os.path.join(REPO_ROOT, "data/fact_db/mechanics/uniques.jsonl")
SETS_PATH = os.path.join(REPO_ROOT, "data/fact_db/mechanics/sets.jsonl")
ALL_PATHS = [UNIQUES_PATH, SETS_PATH]


class TestUniquesDB:
    def test_shako_found_english(self):
        results = search_mechanics("Harlequin Crest Shako", paths=ALL_PATHS)
        assert any("Shako" in r.record.canonical_name or "Harlequin" in r.record.canonical_name for r in results), \
            "Shako should be found by English name"

    def test_shako_found_chinese(self):
        results = search_mechanics("小丑帽 属性", paths=ALL_PATHS)
        assert len(results) > 0, "Shako should be found by Chinese alias 小丑帽"
        ids = [r.record.id for r in results]
        assert "unique.shako" in ids

    def test_soj_found(self):
        results = search_mechanics("Stone of Jordan SoJ", paths=ALL_PATHS)
        assert any(r.record.id == "unique.soj" for r in results)

    def test_soj_chinese(self):
        results = search_mechanics("约旦之石怎么刷", paths=ALL_PATHS)
        assert any(r.record.id == "unique.soj" for r in results)

    def test_arachnid_mesh(self):
        results = search_mechanics("Arachnid Mesh belt caster", paths=ALL_PATHS)
        assert any(r.record.id == "unique.arachnid_mesh" for r in results)

    def test_griffons_eye(self):
        results = search_mechanics("Griffon's Eye lightning sorceress", paths=ALL_PATHS)
        assert any(r.record.id == "unique.griffons" for r in results)

    def test_war_traveler(self):
        results = search_mechanics("War Traveler boots MF", paths=ALL_PATHS)
        assert any(r.record.id == "unique.wartravs" for r in results)

    def test_war_traveler_chinese(self):
        results = search_mechanics("战旅靴子魔法找到率", paths=ALL_PATHS)
        assert any(r.record.id == "unique.wartravs" for r in results)


class TestSetsDB:
    def test_tal_rasha_set(self):
        results = search_mechanics("Tal Rasha's Wrappings MF set sorceress", paths=ALL_PATHS)
        assert any(r.record.id == "set.tal_rasha_wrappings" for r in results)

    def test_tal_rasha_chinese(self):
        results = search_mechanics("塔拉夏套装魔法找到率", paths=ALL_PATHS)
        assert any(r.record.id == "set.tal_rasha_wrappings" for r in results)

    def test_immortal_king(self):
        results = search_mechanics("Immortal King IK Barbarian set", paths=ALL_PATHS)
        assert any(r.record.id == "set.immortal_king" for r in results)

    def test_immortal_king_chinese(self):
        results = search_mechanics("不朽之王套装野蛮人", paths=ALL_PATHS)
        assert any(r.record.id == "set.immortal_king" for r in results)

    def test_natalya_set(self):
        results = search_mechanics("Natalya's Odium Assassin set", paths=ALL_PATHS)
        assert any(r.record.id == "set.natalya" for r in results)

    def test_sigons_set(self):
        results = search_mechanics("Sigon twink set low level", paths=ALL_PATHS)
        assert any(r.record.id == "set.sigons_complete_steel" for r in results)


class TestNewUniques:
    def test_shaftstop_english(self):
        results = search_mechanics("Shaft Stop damage reduction armor", paths=ALL_PATHS)
        assert any(r.record.id == "unique.shaftstop" for r in results)

    def test_shaftstop_chinese(self):
        results = search_mechanics("减伤甲暗金防具", paths=ALL_PATHS)
        assert any(r.record.id == "unique.shaftstop" for r in results)

    def test_verdungos_english(self):
        results = search_mechanics("Verdungo's Heartly Cord belt DR", paths=ALL_PATHS)
        assert any(r.record.id == "unique.verdungos" for r in results)

    def test_verdungos_chinese(self):
        results = search_mechanics("维丁格腰带减伤", paths=ALL_PATHS)
        assert any(r.record.id == "unique.verdungos" for r in results)

    def test_titans_revenge(self):
        results = search_mechanics("Titan's Revenge javelin Amazon", paths=ALL_PATHS)
        assert any(r.record.id == "unique.titans_revenge" for r in results)

    def test_titans_revenge_chinese(self):
        results = search_mechanics("提坦复仇亚马逊", paths=ALL_PATHS)
        assert any(r.record.id == "unique.titans_revenge" for r in results)

    def test_crown_of_ages(self):
        results = search_mechanics("Crown of Ages CoA helmet DR", paths=ALL_PATHS)
        assert any(r.record.id == "unique.crown_of_ages" for r in results)

    def test_crown_of_ages_chinese(self):
        results = search_mechanics("时代王冠头盔", paths=ALL_PATHS)
        assert any(r.record.id == "unique.crown_of_ages" for r in results)

    def test_nightwings_veil(self):
        results = search_mechanics("Nightwing's Veil cold sorceress", paths=ALL_PATHS)
        assert any(r.record.id == "unique.nightwings_veil" for r in results)

    def test_nightwings_veil_chinese(self):
        results = search_mechanics("夜翼面纱寒冰技能", paths=ALL_PATHS)
        assert any(r.record.id == "unique.nightwings_veil" for r in results)

    def test_jalals_mane(self):
        results = search_mechanics("Jalal's Mane Druid shapeshifter", paths=ALL_PATHS)
        assert any(r.record.id == "unique.jalals_mane" for r in results)

    def test_jalals_mane_chinese(self):
        results = search_mechanics("贾拉尔鬃毛德鲁伊", paths=ALL_PATHS)
        assert any(r.record.id == "unique.jalals_mane" for r in results)

    def test_deaths_fathom(self):
        results = search_mechanics("Death's Fathom cold sorceress orb", paths=ALL_PATHS)
        assert any(r.record.id == "unique.deaths_fathom" for r in results)

    def test_trang_claws(self):
        results = search_mechanics("Trang-Oul's Claws Necromancer gloves FCR", paths=ALL_PATHS)
        assert any(r.record.id == "unique.trang_ouls_claws" for r in results)

    def test_trang_claws_chinese(self):
        results = search_mechanics("特兰格手套死灵法师", paths=ALL_PATHS)
        assert any(r.record.id == "unique.trang_ouls_claws" for r in results)

    # --- New P13 uniques ---
    def test_wisp_projector_en(self):
        results = search_mechanics("Wisp Projector ring lightning absorb MF", paths=ALL_PATHS)
        assert any(r.record.id == "unique.wisp_projector" for r in results)

    def test_wisp_projector_cn(self):
        results = search_mechanics("幽灵投影 闪电吸收 魔法找到率", paths=ALL_PATHS)
        assert any(r.record.id == "unique.wisp_projector" for r in results)

    def test_string_of_ears_en(self):
        results = search_mechanics("String of Ears physical damage reduce belt", paths=ALL_PATHS)
        assert any(r.record.id == "unique.string_of_ears" for r in results)

    def test_string_of_ears_cn(self):
        results = search_mechanics("耳环腰带 减伤 物理", paths=ALL_PATHS)
        assert any(r.record.id == "unique.string_of_ears" for r in results)

    def test_magefist_en(self):
        results = search_mechanics("Magefist FCR fire sorceress gloves", paths=ALL_PATHS)
        assert any(r.record.id == "unique.magefist" for r in results)

    def test_magefist_cn(self):
        results = search_mechanics("魔法拳套 法师手套 施法速度", paths=ALL_PATHS)
        assert any(r.record.id == "unique.magefist" for r in results)

    def test_frostburn_en(self):
        results = search_mechanics("Frostburn gloves mana energy shield sorceress", paths=ALL_PATHS)
        assert any(r.record.id == "unique.frostburn" for r in results)

    def test_frostburn_cn(self):
        results = search_mechanics("寒霜拳套 蓝量手套 能量护盾", paths=ALL_PATHS)
        assert any(r.record.id == "unique.frostburn" for r in results)

    def test_gore_rider_en(self):
        results = search_mechanics("Gore Rider boots deadly strike crushing blow melee", paths=ALL_PATHS)
        assert any(r.record.id == "unique.gore_rider" for r in results)

    def test_gore_rider_cn(self):
        results = search_mechanics("血腥骑士靴子近战DS", paths=ALL_PATHS)
        assert any(r.record.id == "unique.gore_rider" for r in results)

    def test_peasant_crown_en(self):
        results = search_mechanics("Peasant Crown MF helm +1 all skills", paths=ALL_PATHS)
        assert any(r.record.id == "unique.peasant_crown" for r in results)

    def test_peasant_crown_cn(self):
        results = search_mechanics("农民冠 魔法找到率 全技能 头盔", paths=ALL_PATHS)
        assert any(r.record.id == "unique.peasant_crown" for r in results)

    def test_twitchthroe_en(self):
        results = search_mechanics("Twitchthroe MF armor IAS FHR melee", paths=ALL_PATHS)
        assert any(r.record.id == "unique.twitchthroe" for r in results)

    def test_twitchthroe_cn(self):
        results = search_mechanics("抽搐胸甲 魔法找到率 攻速 hit recovery", paths=ALL_PATHS)
        assert any(r.record.id == "unique.twitchthroe" for r in results)

    def test_doombringer_en(self):
        results = search_mechanics("Doombringer sword deadly strike ignore target defense barb", paths=ALL_PATHS)
        assert any(r.record.id == "unique.doombringer" for r in results)

    def test_doombringer_cn(self):
        results = search_mechanics("毁灭者巨剑 无视防御 野蛮人", paths=ALL_PATHS)
        assert any(r.record.id == "unique.doombringer" for r in results)

    def test_arreats_face_en(self):
        results = search_mechanics("Arreat's Face barbarian helm +2 skills all res", paths=ALL_PATHS)
        assert any(r.record.id == "unique.arreats_face" for r in results)

    def test_arreats_face_cn(self):
        results = search_mechanics("巴面 阿瑞特之颜 野蛮人头盔 全抗", paths=ALL_PATHS)
        assert any(r.record.id == "unique.arreats_face" for r in results)

    def test_baranars_star_en(self):
        results = search_mechanics("Baranar's Star mace unique elemental damage barb", paths=ALL_PATHS)
        assert any(r.record.id == "unique.baranars_star" for r in results)

    def test_baranars_star_cn(self):
        results = search_mechanics("巴纳之星 晨星 野蛮人武器 火焰闪电冰冷伤害", paths=ALL_PATHS)
        assert any(r.record.id == "unique.baranars_star" for r in results)

    def test_grandfather_en(self):
        results = search_mechanics("The Grandfather two-hand sword deadly strike barb", paths=ALL_PATHS)
        assert any(r.record.id == "unique.grandfather" for r in results)

    def test_grandfather_cn(self):
        results = search_mechanics("老爷剑 双手剑 野蛮人 致命一击 enhanced damage", paths=ALL_PATHS)
        assert any(r.record.id == "unique.grandfather" for r in results)

    def test_thunderstroke_en(self):
        results = search_mechanics("Thunderstroke Amazon lightning fury javelin unique", paths=ALL_PATHS)
        assert any(r.record.id == "unique.thunderstroke" for r in results)

    def test_thunderstroke_cn(self):
        results = search_mechanics("雷矛 雷击矛 亚马逊 闪电怒火 -敌人闪电抗性", paths=ALL_PATHS)
        assert any(r.record.id == "unique.thunderstroke" for r in results)

    def test_blackbogs_sharp_en(self):
        results = search_mechanics("Blackbog's Sharp Necromancer poison nova dagger -enemy resist", paths=ALL_PATHS)
        assert any(r.record.id == "unique.blackbogs_sharp" for r in results)

    def test_blackbogs_sharp_cn(self):
        results = search_mechanics("黑沼毒刃 术士 毒新星 -毒抗 匕首", paths=ALL_PATHS)
        assert any(r.record.id == "unique.blackbogs_sharp" for r in results)

    # P20: Manald Heal, Metalgrid, Cat's Eye, Crescent Moon, Nature's Peace

    def test_manald_heal_en(self):
        results = search_mechanics("Manald Heal ring mana regenerate", paths=ALL_PATHS)
        assert any(r.record.id == "unique.manald_heal" for r in results), \
            "Manald Heal should be found by English name"

    def test_manald_heal_cn(self):
        results = search_mechanics("曼纳 回蓝 戒指 施法者", paths=ALL_PATHS)
        assert any(r.record.id == "unique.manald_heal" for r in results), \
            "Manald Heal should be found by CN alias 曼纳"

    def test_metalgrid_en(self):
        results = search_mechanics("Metalgrid amulet all resistances", paths=ALL_PATHS)
        assert any(r.record.id == "unique.metalgrid" for r in results), \
            "Metalgrid should be found by English name"

    def test_metalgrid_cn(self):
        results = search_mechanics("金属网格 全抗 项链 护身符", paths=ALL_PATHS)
        assert any(r.record.id == "unique.metalgrid" for r in results), \
            "Metalgrid should be found by CN alias 金属网格"

    def test_cats_eye_en(self):
        results = search_mechanics("Cat's Eye amulet attack speed Amazon bowazon", paths=ALL_PATHS)
        assert any(r.record.id == "unique.cats_eye" for r in results), \
            "Cat's Eye should be found by English name"

    def test_cats_eye_cn(self):
        results = search_mechanics("猫眼 弓手 项链 攻击速度 亚马逊", paths=ALL_PATHS)
        assert any(r.record.id == "unique.cats_eye" for r in results), \
            "Cat's Eye should be found by CN alias 猫眼"

    def test_crescent_moon_en(self):
        results = search_mechanics("Crescent Moon amulet FCR mana caster", paths=ALL_PATHS)
        assert any(r.record.id == "unique.crescent_moon" for r in results), \
            "Crescent Moon (amulet) should be found by English name"

    def test_crescent_moon_cn(self):
        results = search_mechanics("月牙 月亮戒 施法者 加速施法", paths=ALL_PATHS)
        assert any(r.record.id == "unique.crescent_moon" for r in results), \
            "Crescent Moon should be found by CN alias 月牙"

    def test_natures_peace_en(self):
        results = search_mechanics("Nature's Peace ring prevent monster revival", paths=ALL_PATHS)
        assert any(r.record.id == "unique.natures_peace" for r in results), \
            "Nature's Peace should be found by English name"

    def test_natures_peace_cn(self):
        results = search_mechanics("自然之和 防止怪物复活 骷髅 戒指", paths=ALL_PATHS)
        assert any(r.record.id == "unique.natures_peace" for r in results), \
            "Nature's Peace should be found by CN alias 自然之和"
