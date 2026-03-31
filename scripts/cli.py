from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from d2r_agent.interactive_session import (
    SessionState,
    load_session_state,
    save_session_state,
    should_resume_from_state,
    normalize_field_value,
    apply_followup_to_ctx,
)
from d2r_agent.orchestrator import answer


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="D2R Agent CLI (MVP)")
    ap.add_argument("query", help="your D2R question")
    ap.add_argument(
        "--ctx",
        help='optional JSON context, e.g. {"release_track":"d2r_roitw","season_id":"current","ladder_flag":"ladder","mode":"SC","platform":"PC","offline":false}',
        default=None,
    )
    ap.add_argument(
        "--interactive",
        action="store_true",
        help="prompt for missing context / follow-ups and re-run answer(); persists a tiny session state so you can reply with just the answer",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="print machine-readable JSON: {text, trace_path, answer:{...including followups}}",
    )
    ap.add_argument(
        "--session-file",
        default="cache/session_state.json",
        help='where to persist interactive state (default: cache/session_state.json)',
    )
    ap.add_argument(
        "--reset-session",
        action="store_true",
        help="ignore any existing session state and start fresh",
    )

    args = ap.parse_args(argv)

    # Base ctx from CLI JSON.
    ctx: dict = {}
    if args.ctx:
        ctx = json.loads(args.ctx)

    if not args.interactive:
        out, trace_path = answer(args.query, ctx)
        if not args.json:
            print(out)
            return 0

        # Best-effort: pull the structured Answer (incl. followups) from the trace events.
        ans_obj = None
        try:
            trace_obj = json.loads(Path(str(trace_path)).read_text(encoding="utf-8"))
            for ev in trace_obj.get("events") or []:
                if ev.get("step") == "answer_compose":
                    ans_obj = ev.get("output")
        except Exception:
            ans_obj = None

        print(
            json.dumps(
                {
                    "text": out,
                    "trace_path": str(trace_path),
                    "answer": ans_obj,
                },
                ensure_ascii=False,
            )
        )
        return 0

    # Interactive mode
    state = SessionState()
    if not args.reset_session:
        state = load_session_state(args.session_file)

    user_query = args.query

    # If user replies with a short answer and we have a pending question, resume.
    if should_resume_from_state(user_query, state) and not args.ctx:
        base_query = state.last_user_query
        ctx = dict(state.ctx or {})
        # Treat the CLI query as the answer to the pending next-step question.
        pending_q = state.pending_next_step_question or (state.pending_questions_to_ask[-1] if state.pending_questions_to_ask else "")
        ctx = apply_followup_to_ctx(ctx, question=str(pending_q), answer=str(user_query))
        user_query = base_query + "\nFollow-up: " + str(user_query)

    interactive_loop_used = False

    # Loop at most twice: initial + one follow-up rerun (keeps CLI predictable).
    for _round in range(2):
        out, trace_path = answer(user_query, ctx, interactive_loop_used=interactive_loop_used)
        print(out)

        # Load trace JSON to see if there are follow-up questions.
        try:
            trace_obj = json.loads(Path(str(trace_path)).read_text(encoding="utf-8"))
        except Exception:
            trace_obj = {}

        missing_fields = list(trace_obj.get("missing_fields") or [])
        questions_to_ask = list(trace_obj.get("questions_to_ask") or [])

        next_step_q_text = trace_obj.get("next_step_question")

        # Persist session state for short follow-up replies.
        state = SessionState(
            last_user_query=user_query.split("\nFollow-up:")[0] if "\nFollow-up:" in user_query else user_query,
            ctx=dict(ctx or {}),
            pending_missing_fields=missing_fields,
            pending_questions_to_ask=questions_to_ask,
            pending_next_step_question=next_step_q_text,
            last_trace_path=str(trace_path),
        )
        save_session_state(args.session_file, state)

        # Decide whether to prompt.
        if not (missing_fields or questions_to_ask or next_step_q_text):
            return 0

        # Prompt for missing structured ctx fields.
        if missing_fields:
            for f in missing_fields:
                try:
                    raw = input(f"{f}? (empty to skip) ").strip()
                except EOFError:
                    raw = ""
                val = normalize_field_value(f, raw)
                if val is not None:
                    ctx[f] = val
                    interactive_loop_used = True

        # Prompt for next-step question (optional; Enter to skip).
        if next_step_q_text:
            try:
                raw2 = input(f"{next_step_q_text} (Enter to skip) ").strip()
            except EOFError:
                raw2 = ""
            if raw2:
                ctx = apply_followup_to_ctx(ctx, question=str(next_step_q_text), answer=str(raw2))
                user_query = state.last_user_query + "\nFollow-up: " + str(raw2)
                interactive_loop_used = True
                continue

        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
