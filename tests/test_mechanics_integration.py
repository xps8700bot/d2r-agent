import pytest
from d2r_agent.orchestrator import answer

def test_mechanics_query_nihlathak():
    # Test Nihlathak farming query
    query = "尼拉萨克 怎么刷？"
    result_text, trace_path = answer(query)
    
    # Check if Nihlathak specific mechanics are found
    assert "Nihlathak" in result_text or "尼拉萨克" in result_text
    assert "Corpse Explosion" in result_text or "尸体爆炸" in result_text
    # Evidence should be present
    assert "theamazonbasin.com" in result_text

def test_mechanics_query_cow_level():
    # Test Cow Level entry query
    query = "如何去奶牛关？"
    result_text, trace_path = answer(query)
    
    assert "Cow Level" in result_text or "奶牛关" in result_text
    assert "Wirt's Leg" in result_text or "维特之脚" in result_text
    assert "Tome of Town Portal" in result_text

def test_runeword_recipe_still_works():
    # Ensure we didn't break runeword logic
    query = "精神 盾 怎么做？"
    result_text, trace_path = answer(query)
    
    assert "Tal + Thul + Ort + Amn" in result_text
    assert "Spirit" in result_text
