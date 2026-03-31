import sys
import os

# Add src to path
sys.path.insert(0, "/home/chen/.openclaw/workspace/d2r_agent/src")

from d2r_agent.orchestrator import answer

def test_item_base_archon_plate():
    print("Testing Archon Plate...")
    query = "Archon Plate max sockets and qlvl?"
    result_text, trace_path = answer(query)
    
    assert "Archon Plate" in result_text, f"Archon Plate not in {result_text}"
    assert "sockets: 4" in result_text, f"Max sockets not found in {result_text}"
    assert "qlvl: 84" in result_text, f"qlvl 84 not found in {result_text}"
    print("  OK")

def test_item_base_monarch():
    print("Testing Monarch...")
    query = "君主盾 多少防御 力量要求？"
    result_text, trace_path = answer(query)
    print(f"DEBUG: Result for Monarch: {result_text}")
    with open(trace_path, "r") as f:
        import json
        trace = json.load(f)
        print(f"DEBUG: Intent detected: {trace.get('intent')}")
    assert "Monarch" in result_text or "统治者大盾" in result_text
    assert "Str Req: 156" in result_text
    assert "sockets: 4" in result_text
    print("  OK")

def test_item_base_crystal_sword_breakpoints():
    print("Testing Crystal Sword...")
    query = "Crystal Sword sockets ilvl?"
    result_text, trace_path = answer(query)
    
    assert "Crystal Sword" in result_text
    assert "ilvl_breakpoints" in result_text
    assert "26-40 (4 sockets)" in result_text
    print("  OK")

def test_item_base_phase_blade():
    print("Testing Phase Blade...")
    query = "幻化之刃 机制"
    result_text, trace_path = answer(query)
    print(f"DEBUG: Result for Phase Blade: {result_text}")
    with open(trace_path, "r") as f:
        import json
        trace = json.load(f)
        print(f"DEBUG: Intent detected: {trace.get('intent')}")
    assert "Phase Blade" in result_text or "幻化之刃" in result_text
    assert "Indestructible" in result_text
    assert "sockets: 6" in result_text
    print("  OK")

def test_item_base_gmb():
    print("Testing GMB...")
    query = "大院长 女族长之弓 技能"
    result_text, trace_path = answer(query)
    
    assert "Grand Matriarchal Bow" in result_text or "大院长" in result_text
    assert "+1-3 Bow and Crossbow Skills" in result_text
    print("  OK")

if __name__ == "__main__":
    test_item_base_archon_plate()
    test_item_base_monarch()
    test_item_base_crystal_sword_breakpoints()
    test_item_base_phase_blade()
    test_item_base_gmb()
    print("All item base tests passed!")
