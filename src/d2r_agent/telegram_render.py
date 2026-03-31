"""Telegram answer rendering utilities.

Extracted from telegram_bot.py so they can be unit-tested without the
python-telegram-bot library.
"""
from __future__ import annotations


# Hook patterns: low-value follow-up lines that should be suppressed in
# direct/complete answers.  These invite further questions when the answer
# is already sufficient.
HOOK_PATTERNS: list[str] = [
    "如果你要，我再继续",
    "如果你要，我可以继续",
    "你希望我按",
    "你想让我继续",
    "我可以先给你一个可执行的解题",
    "需要你先确认",
]


def render_telegram_answer(out_text: str) -> str:
    """Collapse verbose CLI-style answer blocks into a direct Telegram-friendly reply.

    Steps:
    1. Parse sections (TL;DR, Evidence, Options, Next step).
    2. Emit TL;DR lines (de-duped) + evidence snippets.
    3. Filter hook lines.
    """
    lines = [ln.rstrip() for ln in out_text.splitlines()]
    section = None
    sections: dict[str, list[str]] = {
        "tldr": [],
        "evidence": [],
        "next": [],
    }

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        low = line.lower()
        if low == "assumptions:":
            section = "skip"
            continue
        if low == "tl;dr":
            section = "tldr"
            continue
        if low == "evidence":
            section = "evidence"
            continue
        if low == "options":
            section = "skip"
            continue
        if low == "next step":
            section = "next"
            continue
        if low.startswith("(trace") or low.startswith("trace"):
            break

        if section in sections:
            if line == "- (none)":
                continue
            if line.startswith("- "):
                sections[section].append(line[2:].strip())
            else:
                sections[section].append(line)

    out: list[str] = []
    seen: set[str] = set()
    for item in sections["tldr"]:
        if item and item not in seen:
            seen.add(item)
            out.append(item)

    if sections["evidence"]:
        out.append("")
        out.append("证据：")
        for item in sections["evidence"][:2]:
            out.append(f"- {item}")

    rendered = "\n".join(out).strip()
    if not rendered:
        return out_text

    # Suppress hook lines.
    filtered_lines: list[str] = []
    for ln in rendered.splitlines():
        if any(hook in ln for hook in HOOK_PATTERNS):
            continue
        filtered_lines.append(ln)

    result = "\n".join(filtered_lines).strip()
    # If filtering removed everything, the answer was entirely low-value hooks.
    # Return the original unrendered text so callers can see something rather than nothing.
    # (In practice this shouldn't happen for well-formed answers with real content.)
    if not result:
        return out_text
    return result
