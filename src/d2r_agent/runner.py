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

            # New assertions for mechanics upgrade (Phase 0+)
            def _as_list(x):
                if x is None:
                    return []
                if isinstance(x, list):
                    return x
                return [x]

            def _get(path: str):
                cur = tr
                for part in path.split("."):
                    if not isinstance(cur, dict):
                        return None
                    cur = cur.get(part)
                return cur

            # Count-based assertions
            m_min = assert_trace.get("mechanics_fact_hits_min")
            if m_min is not None:
                v = _get("mechanics_fact_hits")
                if v is None:
                    failed.append("trace.mechanics_fact_hits missing")
                elif int(v) < int(m_min):
                    failed.append(f"trace.mechanics_fact_hits should be >= {m_min} (got {v})")

            r_min = assert_trace.get("rules_applied_min")
            if r_min is not None:
                v = _get("rules_applied")
                if v is None:
                    failed.append("trace.rules_applied missing")
                else:
                    n = len(v) if isinstance(v, list) else 0
                    if n < int(r_min):
                        failed.append(f"trace.rules_applied length should be >= {r_min} (got {n})")

            # Membership assertions (tier/formula/followups)
            tiers_contains = assert_trace.get("source_tiers_used_contains")
            if tiers_contains is not None:
                tiers = _as_list(_get("source_tiers_used"))
                for need_t in _as_list(tiers_contains):
                    if need_t not in tiers:
                        failed.append(f"trace.source_tiers_used should contain {need_t} (got {tiers})")

            tiers_contains_any = assert_trace.get("source_tiers_used_contains_any")
            if tiers_contains_any is not None:
                tiers = _as_list(_get("source_tiers_used"))
                if not any(t in tiers for t in _as_list(tiers_contains_any)):
                    failed.append(f"trace.source_tiers_used should contain any of {tiers_contains_any} (got {tiers})")

            formulas_any = assert_trace.get("formulas_used_contains_any")
            if formulas_any is not None:
                formulas = _as_list(_get("formulas_used"))
                if not any(any(str(k).lower() in str(f).lower() for f in formulas) for k in _as_list(formulas_any)):
                    failed.append(f"trace.formulas_used should contain any of {formulas_any} (got {formulas})")

            follow_any = assert_trace.get("followup_fields_requested_contains_any")
            if follow_any is not None:
                fields = _as_list(_get("followup_fields_requested"))
                if not any(f in fields for f in _as_list(follow_any)):
                    failed.append(f"trace.followup_fields_requested should contain any of {follow_any} (got {fields})")

            # Output section assertions
            out_sections = assert_trace.get("output_sections_must_contain")
            if out_sections is not None:
                for sec in _as_list(out_sections):
                    if sec not in out:
                        failed.append(f"output should contain section header: {sec}")

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
