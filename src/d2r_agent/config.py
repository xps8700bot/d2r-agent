from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentDefaults:
    # Release/season governance are first-class: defaults must be explicit.
    # User preference: default to the Warlock-era track, latest season, Ladder HC online (Bnet)
    # unless explicitly overridden by user ctx.
    release_track: str = "d2r_roitw"   # 术士君临版本
    season_id: str | None = "current" # 默认最新赛季（在 merge_ctx 中解析）

    ladder_flag: str = "ladder"       # ladder|non-ladder|offline|unknown
    mode: str = "HC"                  # SC|HC
    platform: str = "PC"              # PC|Switch|PS|Xbox
    offline: bool | None = False       # online(Bnet)


DEFAULTS = AgentDefaults()

# 阶段 B 会扩展为可配置文件；MVP 先写死在代码里
WHITELIST_DOMAINS: list[str] = [
    # MediaWiki (优先，用 API/REST 可抽取可引用片段)
    "theamazonbasin.com",
    "www.theamazonbasin.com",

    # 其他资料站（阶段 B 后续可逐个加 adapter）
    "maxroll.gg",
    "diablo2.io",
    "diablo2.wiki.fextralife.com",
]

# Official (fallback-only) sources for season/ladder rule changes
OFFICIAL_WHITELIST_DOMAINS: list[str] = [
    # Blizzard News (authoritative season announcements / patch notes)
    "news.blizzard.com",
    # Official forums (fallback)
    "us.forums.blizzard.com",
]

HTTP_TIMEOUT_S = 12
HTTP_MAX_RETRIES = 2

CACHE_DIR = "cache"
TRACES_DIR = "traces"
MEMORY_PATH = "data/memory.jsonl"
