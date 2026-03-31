from __future__ import annotations

from d2r_agent.orchestrator import answer
from d2r_agent.config import DEFAULTS


def test_build_compare_insight_spirit_does_not_ask_release_track() -> None:
    q = "69级召唤术士应该拿眼光还是精神?"
    ctx = {
        "release_track": DEFAULTS.release_track,
        "season_id": DEFAULTS.season_id,
        "ladder_flag": DEFAULTS.ladder_flag,
        "mode": DEFAULTS.mode,
        "platform": DEFAULTS.platform,
        "offline": DEFAULTS.offline,
    }
    out, _trace = answer(q, ctx)

    # Ensure the default fallback question isn't asking for release_track again.
    assert "release_track" not in out.split("\n\nNext step\n", 1)[-1]
    assert "你是打算给自己用" in out
