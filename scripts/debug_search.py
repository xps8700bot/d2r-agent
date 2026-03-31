import sys
import os
import json

# Add src to path
sys.path.insert(0, "/home/chen/.openclaw/workspace/d2r_agent/src")

from d2r_agent.knowledge.mechanics_db import search_mechanics, _tokenize

repo_root = "/home/chen/.openclaw/workspace/d2r_agent"
mechanics_paths = [
    os.path.join(repo_root, "data/fact_db/mechanics/treasure_class.jsonl"),
    os.path.join(repo_root, "data/fact_db/mechanics/item_bases.jsonl"),
]

query = "君主盾 多少防御 力量要求？"
tokens = _tokenize(query)
print(f"Tokens: {tokens}")

from d2r_agent.knowledge.mechanics_db import search_mechanics
hits = search_mechanics(query, paths=mechanics_paths)
print(f"Hits found: {len(hits)}")
for h in hits:
    print(f"Score: {h.score}, Name: {h.record.canonical_name}")
