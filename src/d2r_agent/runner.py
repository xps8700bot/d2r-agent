from __future__ import annotations

import sys
from pathlib import Path

import yaml

from d2r_agent.orchestrator import answer


def run_regression(cases_path: str) -> int:
    cases = yaml.safe_load(Path(cases_path).read_text(encoding="utf-8"))
    if not cases:
        print("no cases")
        return 0

    ok = 0
    for c in cases:
        cid = c.get("id", "?")
        q = c["query"]
        must = c.get("must_contain", [])
        assert_trace = c.get("assert_trace", None) or {}

        out, trace_path = answer(q)

        failed = [m for m in must if m not in out]

        # Optional trace assertions
        if assert_trace:
            import json

            tr = json.loads(Path(trace_path).read_text(encoding="utf-8"))
            intent_not = assert_trace.get("intent_not")
            if intent_not and tr.get("intent") == intent_not:
                failed.append(f"trace.intent should not be {intent_not}")

            intent_is = assert_trace.get("intent_is")
            if intent_is and tr.get("intent") != intent_is:
                failed.append(f"trace.intent should be {intent_is} (got {tr.get('intent')})")

            intent_in = assert_trace.get("intent_in")
            if intent_in and tr.get("intent") not in intent_in:
                failed.append(f"trace.intent should be in {intent_in} (got {tr.get('intent')})")

            retrieval_needed_is = assert_trace.get("retrieval_needed_is", None)
            if retrieval_needed_is is not None and tr.get("retrieval_needed") != retrieval_needed_is:
                failed.append(f"trace.retrieval_needed should be {retrieval_needed_is} (got {tr.get('retrieval_needed')})")

            evidence_count_is = assert_trace.get("evidence_count_is", None)
            if evidence_count_is is not None:
                facts = (tr.get("extracted_facts") or {}).get("facts") or []
                if len(facts) != evidence_count_is:
                    failed.append(f"trace.extracted_facts.facts length should be {evidence_count_is} (got {len(facts)})")

            if assert_trace.get("memory_written_empty") is True:
                if (tr.get("memory_written") or {}) != {}:
                    failed.append("trace.memory_written should be empty")

        if failed:
            print(f"FAIL {cid}: {failed}")
        else:
            ok += 1
            print(f"OK   {cid}")

    total = len(cases)
    print(f"\npass: {ok}/{total}")
    return 0 if ok == total else 1


if __name__ == "__main__":
    p = "src/d2r_agent/eval/regression_cases.yaml"
    sys.exit(run_regression(p))
