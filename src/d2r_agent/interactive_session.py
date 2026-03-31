from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class SessionState:
    """Minimal persisted CLI state so a user can reply with just an answer.

    This is intentionally weakly-typed because ctx is an open dict.
    """

    last_user_query: str = ""
    ctx: dict[str, Any] = field(default_factory=dict)

    # "Pending" here means: the last run produced follow-up questions.
    pending_missing_fields: list[str] = field(default_factory=list)
    pending_questions_to_ask: list[str] = field(default_factory=list)
    pending_next_step_question: str | None = None

    last_trace_path: str | None = None


def load_session_state(path: str) -> SessionState:
    p = Path(path)
    if not p.exists():
        return SessionState()
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return SessionState()

    return SessionState(
        last_user_query=str(obj.get("last_user_query") or ""),
        ctx=dict(obj.get("ctx") or {}),
        pending_missing_fields=list(obj.get("pending_missing_fields") or []),
        pending_questions_to_ask=list(obj.get("pending_questions_to_ask") or []),
        pending_next_step_question=(obj.get("pending_next_step_question") or None),
        last_trace_path=(obj.get("last_trace_path") or None),
    )


def save_session_state(path: str, state: SessionState) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {
                "last_user_query": state.last_user_query,
                "ctx": state.ctx,
                "pending_missing_fields": state.pending_missing_fields,
                "pending_questions_to_ask": state.pending_questions_to_ask,
                "pending_next_step_question": state.pending_next_step_question,
                "last_trace_path": state.last_trace_path,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def looks_like_followup_only(user_input: str) -> bool:
    s = (user_input or "").strip()
    if not s:
        return False
    # Heuristic: short and single-line => likely a direct answer like "B" / "SC" / "给自己用".
    if "\n" in s or "\r" in s:
        return False
    return len(s) <= 80


def should_resume_from_state(user_query: str, state: SessionState) -> bool:
    if not state.last_user_query:
        return False
    if not (state.pending_questions_to_ask or state.pending_next_step_question or state.pending_missing_fields):
        return False
    return looks_like_followup_only(user_query)


def normalize_field_value(field: str, raw: str) -> Any:
    v = (raw or "").strip()
    if v == "":
        return None

    if field == "mode":
        up = v.upper()
        if up in {"SC", "SOFTCORE", "软核"}:
            return "SC"
        if up in {"HC", "HARDCORE", "硬核"}:
            return "HC"
        return v

    if field == "offline":
        low = v.lower()
        if low in {"true", "t", "1", "yes", "y", "离线", "offline"}:
            return True
        if low in {"false", "f", "0", "no", "n", "在线", "online"}:
            return False
        return v

    if field == "ladder_flag":
        low = v.lower()
        if low in {"ladder", "l", "天梯"}:
            return "ladder"
        if low in {"non-ladder", "nonladder", "nl", "非天梯"}:
            return "non-ladder"
        if low in {"offline", "单机", "离线"}:
            # We don't force offline=True here; caller can set offline separately.
            return "offline"
        return v

    # release_track, season_id, platform: return as-is
    return v


def apply_followup_to_ctx(ctx: dict[str, Any], *, question: str, answer: str) -> dict[str, Any]:
    # Keep it lightweight and append-only.
    out = dict(ctx or {})
    hist = list(out.get("_followups") or [])
    hist.append({"q": question, "a": answer})
    out["_followups"] = hist
    return out


def simulate_interactive_flow(
    *,
    initial_query: str,
    initial_ctx: dict[str, Any] | None,
    scripted_inputs: list[str],
    answer_fn: Callable[[str, dict[str, Any], bool], tuple[str, dict[str, Any]]],
) -> tuple[str, dict[str, Any]]:
    """Deterministic, side-effect-free simulation.

    `answer_fn(query, ctx, interactive_loop_used)` should return (out_text, trace_like_dict)
    where trace_like_dict includes keys: missing_fields, questions_to_ask, next_step_question.
    """

    ctx = dict(initial_ctx or {})
    q = initial_query
    interactive_used = False

    def _next_input() -> str:
        if not scripted_inputs:
            raise RuntimeError("scripted_inputs exhausted")
        return scripted_inputs.pop(0)

    while True:
        out, trace = answer_fn(q, ctx, interactive_used)
        missing_fields = list(trace.get("missing_fields") or [])
        questions_to_ask = list(trace.get("questions_to_ask") or [])
        next_q = trace.get("next_step_question")

        if not (missing_fields or questions_to_ask or next_q):
            return out, ctx

        # Fill missing fields (one prompt per field).
        for f in missing_fields:
            raw = _next_input()
            val = normalize_field_value(f, raw)
            if val is not None:
                ctx[f] = val
                interactive_used = True

        # Optional: answer next-step question (empty means skip)
        if next_q:
            raw2 = _next_input()
            if (raw2 or "").strip():
                ctx = apply_followup_to_ctx(ctx, question=str(next_q), answer=str(raw2))
                q = q + "\nFollow-up: " + str(raw2)
                interactive_used = True
            else:
                return out, ctx
