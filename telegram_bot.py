"""Standalone Telegram bot wrapper for d2r_agent.

Requirements:
  pip install python-telegram-bot

Env:
  export D2R_TELEGRAM_BOT_TOKEN=...

Run:
  python telegram_bot.py

Notes:
- Uses python-telegram-bot v20+ async API.
- On each user text message:
  1) reply "⏳ 查询中…"
  2) call d2r_agent.orchestrator.answer()
  3) reply with the answer text
- Inline followup buttons are preserved using existing d2r_agent.telegram_followups logic.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

# Ensure `import d2r_agent` works when running from repo root.
REPO_ROOT = Path(__file__).resolve().parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from d2r_agent.orchestrator import answer
from d2r_agent.retrieval_router import route
from d2r_agent.detectors.context_gap import detect_context_gaps
from d2r_agent.followups import build_followups
from d2r_agent.telegram_followups import decode_ctx_patch
from d2r_agent.telegram_render import render_telegram_answer
from d2r_agent.telegram_session_state import apply_patch_and_rerun, upsert_session
from d2r_agent.config import DEFAULTS


log = logging.getLogger("d2r_agent.telegram_bot")

# Where we persist chat state (last query + ctx) for callback followups.
STATE_PATH = str(REPO_ROOT / "data" / "telegram_sessions.json")
MEMORY_DIR = REPO_ROOT / "data" / "telegram_memory"


def _followups_to_markup(followups: list[Any] | None) -> InlineKeyboardMarkup | None:
    if not followups:
        return None

    rows: list[list[InlineKeyboardButton]] = []
    for fu in followups:
        row: list[InlineKeyboardButton] = []
        for ch in getattr(fu, "choices", []) or []:
            label = getattr(ch, "label", None)
            cb = getattr(ch, "ctxPatch", None)
            if not label:
                continue
            # callback_data must be small; encode_ctx_patch is used in d2r_agent.telegram_followups
            # but we can reuse its output via encode_ctx_patch implicitly by calling followups_to_inline_keyboard.
            # Here we replicate the minimal part by using the existing encode function through that module.
            from d2r_agent.telegram_followups import encode_ctx_patch

            row.append(InlineKeyboardButton(text=str(label), callback_data=encode_ctx_patch(dict(cb or {}))))
        if row:
            rows.append(row)

    return InlineKeyboardMarkup(rows) if rows else None


def _append_chat_log(chat_id: str | int, role: str, text: str) -> None:
    """Append raw chat messages to a per-chat jsonl file."""

    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    path = MEMORY_DIR / f"chat_{chat_id}.jsonl"
    import json, time

    rec = {"ts": int(time.time()), "role": role, "text": text}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _load_compact_summary(chat_id: str | int, *, max_chars: int = 1200, tail_lines: int = 120) -> str:
    """Load a compact in-chat memory summary.

    We keep it simple and deterministic: take recent log lines and truncate.
    This avoids calling any LLM just to maintain memory.
    """

    path = MEMORY_DIR / f"chat_{chat_id}.jsonl"
    if not path.exists():
        return ""

    # Read tail_lines from the end (cheap approximation: read whole file if small).
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-tail_lines:]
    except Exception:
        return ""

    # Keep only user-provided text as memory signal.
    import json

    chunks: list[str] = []
    for ln in lines:
        try:
            obj = json.loads(ln)
        except Exception:
            continue
        if obj.get("role") == "user":
            t = str(obj.get("text") or "").strip()
            if t:
                chunks.append(t)

    s = "\n".join(chunks)
    if len(s) > max_chars:
        s = s[-max_chars:]
    return s




def _render_telegram_answer(out_text: str) -> str:
    """Collapse verbose CLI-style answer blocks into a direct Telegram-friendly reply.

    Delegates to d2r_agent.telegram_render.render_telegram_answer for testability.
    """
    return render_telegram_answer(out_text)

def _default_user_ctx() -> dict[str, Any]:
    """Default context for Telegram bot.

    Goal: don't pester user for defaults (release_track/season/mode/platform, etc.).
    Users can still override explicitly by typing it.
    """

    return {
        "release_track": DEFAULTS.release_track,
        "season_id": DEFAULTS.season_id,
        "ladder_flag": DEFAULTS.ladder_flag,
        "mode": DEFAULTS.mode,
        "platform": DEFAULTS.platform,
        "offline": DEFAULTS.offline,
    }


def _compute_followups_for_query(user_query: str, user_ctx: dict[str, Any] | None) -> list[Any] | None:
    """Recompute followups so we can render inline keyboard.

    orchestrator.answer() returns only text+trace_path, so we recompute the followup structure
    (missing fields + expected entities) using the same building blocks.
    """

    merged_ctx = dict(_default_user_ctx())
    merged_ctx.update(user_ctx or {})

    gap = detect_context_gaps(user_query, merged_ctx)
    rr = route(user_query, gap.intent, current_date=None, release_track=str(merged_ctx.get("release_track") or ""))
    followups = build_followups(
        missing_fields=gap.missing_fields,
        intent=gap.intent,
        entities=rr.expected_entities,
        ctx=merged_ctx,
    )
    return followups or None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text("欢迎使用 d2r-agent。直接发问题即可，我会尽量给出可验证的答案。")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    token = os.environ.get("D2R_TELEGRAM_BOT_TOKEN")
    if not token:
        # Should not happen if bot is running, but keep a friendly error.
        await update.message.reply_text("❌ 服务器未配置 D2R_TELEGRAM_BOT_TOKEN")
        return

    user_query = update.message.text.strip()
    if not user_query:
        return

    chat_id = update.effective_chat.id if update.effective_chat else None

    await update.message.reply_text("⏳ 查询中…")

    # Persist raw chat history (in-chat memory).
    if chat_id is not None:
        _append_chat_log(chat_id, "user", user_query)

    try:
        # Run blocking work in a thread to keep the event loop responsive.
        ctx = _default_user_ctx()
        ctx["concise"] = True
        if chat_id is not None:
            ctx["dialog_summary"] = _load_compact_summary(chat_id)
        out_text, _trace_path = await asyncio.to_thread(answer, user_query, ctx)
        out_text = _render_telegram_answer(out_text)

        # Persist last query for followups.
        if chat_id is not None:
            upsert_session(STATE_PATH, chat_id, last_user_query=user_query, ctx=ctx)

        # Render followup buttons if any.
        followups = await asyncio.to_thread(_compute_followups_for_query, user_query, ctx)
        markup = _followups_to_markup(followups)

        await update.message.reply_text(out_text, reply_markup=markup)

        if chat_id is not None:
            _append_chat_log(chat_id, "assistant", out_text)

    except Exception:
        log.exception("answer() failed")
        await update.message.reply_text("❌ 查询失败，请稍后重试")


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.callback_query:
        return

    q = update.callback_query
    await q.answer()  # remove loading spinner

    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id is None:
        await q.edit_message_text("❌ 无法识别 chat_id")
        return

    try:
        ctx_patch = decode_ctx_patch(q.data or "")
        out_text, _trace_path, sess = await asyncio.to_thread(
            apply_patch_and_rerun,
            state_path=STATE_PATH,
            chat_id=chat_id,
            ctx_patch=ctx_patch,
        )
        out_text = _render_telegram_answer(out_text)

        # Recompute followups for the updated ctx.
        followups = await asyncio.to_thread(_compute_followups_for_query, sess.last_user_query, sess.ctx)
        markup = _followups_to_markup(followups)

        # Update existing message in-place for a clean UX.
        await q.edit_message_text(out_text, reply_markup=markup)

    except Exception:
        log.exception("callback handling failed")
        try:
            await q.edit_message_text("❌ 查询失败，请稍后重试")
        except Exception:
            await q.message.reply_text("❌ 查询失败，请稍后重试")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")

    token = os.environ.get("D2R_TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Missing env D2R_TELEGRAM_BOT_TOKEN")

    app: Application = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
