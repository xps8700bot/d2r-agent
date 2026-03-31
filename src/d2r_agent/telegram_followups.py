from __future__ import annotations

import base64
import json
from typing import Any

from d2r_agent.schemas import Answer


_CALLBACK_PREFIX = "d2r:ctx:"


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * ((4 - (len(s) % 4)) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("ascii"))


def encode_ctx_patch(ctx_patch: dict[str, Any]) -> str:
    """Encode a tiny ctx patch into compact callback_data.

    Format: d2r:ctx:{base64url(json)}

    Note: Telegram callback_data has a size limit (typically 64 bytes). Keep patches tiny.
    """

    payload = json.dumps(ctx_patch, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return _CALLBACK_PREFIX + _b64url_encode(payload)


def decode_ctx_patch(callback_data: str) -> dict[str, Any]:
    if not (callback_data or "").startswith(_CALLBACK_PREFIX):
        raise ValueError("not a d2r ctx callback")
    b64 = callback_data[len(_CALLBACK_PREFIX) :]
    obj = json.loads(_b64url_decode(b64).decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("ctx patch must be a dict")
    return obj


def followups_to_inline_keyboard(
    followups: list[Answer.Followup] | None,
    *,
    max_buttons_per_row: int = 2,
) -> dict[str, Any] | None:
    """Map followups to a Telegram inline_keyboard payload.

    Returns a dict suitable for Telegram Bot API's reply_markup.
    """

    if not followups:
        return None

    rows: list[list[dict[str, str]]] = []

    for fu in followups:
        row: list[dict[str, str]] = []
        for ch in fu.choices:
            row.append(
                {
                    "text": ch.label,
                    "callback_data": encode_ctx_patch(dict(ch.ctxPatch or {})),
                }
            )
            if len(row) >= max_buttons_per_row:
                rows.append(row)
                row = []
        if row:
            rows.append(row)

    return {"inline_keyboard": rows}
