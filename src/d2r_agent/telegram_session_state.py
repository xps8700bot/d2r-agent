from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from d2r_agent.orchestrator import answer


@dataclass
class TelegramSession:
    chat_id: str
    last_user_query: str
    ctx: dict[str, Any]


def _load_all(path: str) -> dict[str, dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _save_all(path: str, obj: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def get_session(path: str, chat_id: str | int) -> TelegramSession | None:
    all_obj = _load_all(path)
    sid = str(chat_id)
    v = all_obj.get(sid)
    if not isinstance(v, dict):
        return None
    q = str(v.get("last_user_query") or "")
    ctx = dict(v.get("ctx") or {})
    if not q:
        return None
    return TelegramSession(chat_id=sid, last_user_query=q, ctx=ctx)


def upsert_session(path: str, chat_id: str | int, *, last_user_query: str, ctx: dict[str, Any]) -> TelegramSession:
    all_obj = _load_all(path)
    sid = str(chat_id)
    sess = TelegramSession(chat_id=sid, last_user_query=last_user_query, ctx=dict(ctx or {}))
    all_obj[sid] = {"last_user_query": sess.last_user_query, "ctx": sess.ctx}
    _save_all(path, all_obj)
    return sess


def apply_ctx_patch(sess: TelegramSession, ctx_patch: dict[str, Any]) -> TelegramSession:
    # Convention: shallow merge.
    new_ctx = dict(sess.ctx or {})
    for k, v in (ctx_patch or {}).items():
        new_ctx[k] = v
    return TelegramSession(chat_id=sess.chat_id, last_user_query=sess.last_user_query, ctx=new_ctx)


def apply_patch_and_rerun(
    *,
    state_path: str,
    chat_id: str | int,
    ctx_patch: dict[str, Any],
) -> tuple[str, str, TelegramSession]:
    """Apply a ctx patch to stored session and re-run the original query.

    Returns: (out_text, trace_path, updated_session)
    """

    sess = get_session(state_path, chat_id)
    if sess is None:
        raise RuntimeError("no session for chat_id; call upsert_session() after the initial user query")

    updated = apply_ctx_patch(sess, ctx_patch)
    out, trace_path = answer(updated.last_user_query, updated.ctx, interactive_loop_used=True)
    upsert_session(state_path, chat_id, last_user_query=updated.last_user_query, ctx=updated.ctx)
    return out, trace_path, updated
