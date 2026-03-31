import pytest
from d2r_agent.orchestrator import answer

def test_item_base_archon_plate():
    # Test Archon Plate lookup
    query = "Archon Plate max sockets and qlvl?"
    result_text, trace_path = answer(query)
    
    assert "Archon Plate" in result_text
    assert "sockets: 4" in result_text
    assert "qlvl: 84" in result_text
    # Evidence should be present
    assert "theamazonbasin.com" in result_text

def test_item_base_monarch():
    # Test Monarch lookup
    query = "君主盾 多少防御 力量要求？"
    result_text, trace_path = answer(query)
    
    assert "Monarch" in result_text or "统治者大盾" in result_text
    assert "Str Req: 156" in result_text
    assert "sockets: 4" in result_text

def test_item_base_crystal_sword_breakpoints():
    # Test ilvl breakpoints for Crystal Sword
    query = "Crystal Sword sockets ilvl?"
    result_text, trace_path = answer(query)
    
    assert "Crystal Sword" in result_text
    assert "ilvl_breakpoints" in result_text
    assert "26-40 (4 sockets)" in result_text

def test_item_base_phase_blade():
    # Test Phase Blade lookup
    query = "幻化之刃 机制"
    result_text, trace_path = answer(query)
    
    assert "Phase Blade" in result_text or "幻化之刃" in result_text
    assert "Indestructible" in result_text
    assert "sockets: 6" in result_text

def test_item_base_gmb():
    # Test Grand Matriarchal Bow lookup
    query = "大院长 女族长之弓 技能"
    result_text, trace_path = answer(query)
    
    assert "Grand Matriarchal Bow" in result_text or "大院长" in result_text
    assert "+1-3 Bow and Crossbow Skills" in result_text


def test_reddit_hot_question_crystal_sword_larzuk_spirit_breakpoint():
    # Reddit-style hot question: can a Normal Crystal Sword become 4os at Larzuk for Spirit?
    query = "Normal cows 掉的 Crystal Sword 拿去 Larzuk 会 4 孔吗，能做 Spirit 吗？"
    result_text, trace_path = answer(query)

    assert "Crystal Sword" in result_text
    assert "26-40 (4 sockets)" in result_text
    assert "Spirit" in result_text
    assert ("Larzuk" in result_text) or ("拉苏克" in result_text)
    # The answer should explicitly connect the breakpoint to the 4os Spirit outcome.
    assert ("4 孔" in result_text) or ("4 sockets" in result_text)
