"""Tests for gems.jsonl knowledge base."""
import os
import pytest
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from d2r_agent.knowledge.mechanics_db import search_mechanics

GEMS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "fact_db", "mechanics", "gems.jsonl"
)


class TestGemsDb:
    def _search(self, query, limit=5):
        return search_mechanics(query, paths=[GEMS_PATH], limit=limit)

    def test_perfect_topaz_mf(self):
        """Perfect Topaz is findable by MF / magic find queries."""
        results = self._search("完美黄宝石 魔法发现")
        assert len(results) > 0
        ids = [r.record.id for r in results]
        assert "gem.perfect_topaz" in ids

    def test_perfect_topaz_en(self):
        results = self._search("perfect topaz magic find")
        assert any(r.record.id == "gem.perfect_topaz" for r in results)

    def test_flawless_topaz(self):
        results = self._search("flawless topaz MF")
        assert any(r.record.id == "gem.flawless_topaz" for r in results)

    def test_perfect_skull_crafting(self):
        results = self._search("perfect skull crafting recipe")
        assert any(r.record.id == "gem.perfect_skull" for r in results)

    def test_perfect_skull_cn(self):
        results = self._search("完美骷髅")
        assert any(r.record.id == "gem.perfect_skull" for r in results)

    def test_gem_upgrade_recipe_exists(self):
        """Gem upgrade recipe entry should exist in the gems DB."""
        import json
        with open(GEMS_PATH) as f:
            records = [json.loads(l) for l in f if l.strip()]
        ids = [r["id"] for r in records]
        assert "gem.cube_upgrade" in ids, "gem.cube_upgrade not found in gems.jsonl"

    def test_gem_upgrade_recipe_by_alias(self):
        """Gem upgrade recipe is retrievable by its aliases."""
        results = self._search("宝石升级 cube gem-upgrade", limit=10)
        # The record has alias "gem upgrade" which should match
        # Note: 'gem upgrade' alias matches via substring scoring
        assert any(r.record.id == "gem.cube_upgrade" for r in results)

    def test_diamond_allres(self):
        results = self._search("diamond shield all resistance")
        assert any(r.record.id == "gem.perfect_diamond" for r in results)

    def test_ruby_life_helm(self):
        """Ruby in helm gives life bonus."""
        results = self._search("ruby life helm")
        assert any(r.record.id == "gem.perfect_ruby" for r in results)

    def test_sapphire_mana(self):
        results = self._search("sapphire mana")
        assert any(r.record.id == "gem.perfect_sapphire" for r in results)


class TestNewUniques:
    """Tests for newly added unique items (Tal's ammy, rings, etc.)."""

    UNIQUES_PATH = os.path.join(
        os.path.dirname(__file__), "..", "data", "fact_db", "mechanics", "uniques.jsonl"
    )

    def _search(self, query, limit=5):
        return search_mechanics(query, paths=[self.UNIQUES_PATH], limit=limit)

    def test_tals_ammy_cn(self):
        results = self._search("塔拉夏护身符")
        assert any(r.record.id == "unique.tals_ammy" for r in results)

    def test_tals_ammy_en(self):
        results = self._search("Tal Rasha adjudication sorceress skills FCR")
        assert any(r.record.id == "unique.tals_ammy" for r in results)

    def test_dwarf_star(self):
        results = self._search("dwarf star fire absorb ring")
        assert any(r.record.id == "unique.dwarf_star" for r in results)

    def test_dwarf_star_cn(self):
        results = self._search("矮星 火免戒")
        assert any(r.record.id == "unique.dwarf_star" for r in results)

    def test_raven_frost_cbf(self):
        results = self._search("raven frost cannot be frozen ring")
        assert any(r.record.id == "unique.raven_frost" for r in results)

    def test_raven_frost_cn(self):
        results = self._search("冰免戒 渡鸦霜")
        assert any(r.record.id == "unique.raven_frost" for r in results)

    def test_bk_ring(self):
        results = self._search("BK ring all skills life leech")
        assert any(r.record.id == "unique.bk_ring" for r in results)

    def test_bk_ring_cn(self):
        results = self._search("BK婚戒 布尔卡索斯")
        assert any(r.record.id == "unique.bk_ring" for r in results)

    def test_highlords(self):
        results = self._search("highlord wrath deadly strike amulet")
        assert any(r.record.id == "unique.highlords" for r in results)

    def test_highlords_cn(self):
        results = self._search("海洛德之怒 致命一击")
        assert any(r.record.id == "unique.highlords" for r in results)

    def test_deaths_fathom_id_fixed(self):
        """Verify the id typo fix: should be lowercase deaths_fathom."""
        results = self._search("death's fathom cold sorceress")
        assert any(r.record.id == "unique.deaths_fathom" for r in results)
        # Confirm old broken id is gone
        assert not any(r.record.id == "unique.Deaths_fathom" for r in results)

    def test_cube_upgrade_cn_variants(self):
        """CJK upgrade recipe aliases hit gem.cube_upgrade reliably."""
        for q in ["升级宝石", "合成宝石", "三颗宝石", "升品", "cube宝石配方"]:
            results = search_mechanics(q, paths=[GEMS_PATH], limit=5)
            ids = [r.record.id for r in results]
            assert "gem.cube_upgrade" in ids, f"cube_upgrade not found for query: {q!r}"

    def test_cube_upgrade_en_variants(self):
        for q in ["gem recipe", "cube gem recipe", "gem upgrade recipe"]:
            results = search_mechanics(q, paths=[GEMS_PATH], limit=5)
            ids = [r.record.id for r in results]
            assert "gem.cube_upgrade" in ids, f"cube_upgrade not found for query: {q!r}"
