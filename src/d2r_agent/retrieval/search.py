from __future__ import annotations

from dataclasses import dataclass

from d2r_agent.config import CACHE_DIR
from d2r_agent.retrieval.adapters.theamazonbasin import BASIN_HOST, basin_search_titles
from d2r_agent.retrieval.whitelist import is_whitelisted


OFFICIAL_NEWS_HOST = "news.blizzard.com"
OFFICIAL_FORUMS_HOST = "us.forums.blizzard.com"


@dataclass
class SearchResult:
    url: str
    title: str
    site: str | None = None
    page_title: str | None = None


def search(keywords: list[str], sites: list[str], cache_dir: str = CACHE_DIR, per_site_limit: int = 5) -> list[SearchResult]:
    """Stage B: site adapters + site-internal search.

    Constraints:
    - Must only return whitelisted URLs.
    - Prefer stable page URLs over generic /search endpoints.

    IMPORTANT:
    - For official Blizzard sites (news/forums), we do NOT fabricate /search?q= URLs.
      If we don't already have a concrete, stable page URL, return nothing for that site.
    """

    out: list[SearchResult] = []

    q = " ".join([k.strip() for k in keywords if k.strip()])[:200]
    if not q:
        return []

    # Respect caller-provided priority order.
    ordered_sites: list[str] = []
    seen = set()
    for s in sites:
        s2 = (s or "").strip().lower()
        if not s2 or s2 in seen:
            continue
        seen.add(s2)
        ordered_sites.append(s2)

    for s in ordered_sites:
        s = s.strip().lower()
        if not s:
            continue

        # Official sites: no synthetic search URLs in MVP.
        if s in {OFFICIAL_NEWS_HOST, OFFICIAL_FORUMS_HOST}:
            continue

        if s == BASIN_HOST:
            try:
                basin_queries = []
                # Prefer individual keywords (often English item name) over a mixed-language combined query.
                for kw in keywords:
                    kw = kw.strip()
                    if kw and kw not in basin_queries:
                        basin_queries.append(kw)
                if q not in basin_queries:
                    basin_queries.append(q)

                seen_titles: set[str] = set()
                for bq in basin_queries[:4]:
                    hits = basin_search_titles(bq, cache_dir=cache_dir, limit=per_site_limit)
                    for h in hits:
                        if h.title.lower() in seen_titles:
                            continue
                        seen_titles.add(h.title.lower())
                        if not is_whitelisted(h.url, sites):
                            continue
                        out.append(SearchResult(url=h.url, title=h.title, site=s, page_title=h.title))
                        if len(out) >= per_site_limit:
                            break
                    if len(out) >= per_site_limit:
                        break
            except Exception:
                # fall back to a generic entry point
                out.append(
                    SearchResult(
                        url=f"https://{s}/wiki/index.php?search={q.replace(' ', '+')}",
                        title=f"{s} search: {q}",
                        site=s,
                    )
                )
            continue

        # Fallback adapter: generate a safe on-site search URL
        url = f"https://{s}/search?q={q.replace(' ', '+')}"
        if is_whitelisted(url, sites):
            out.append(SearchResult(url=url, title=f"{s} search: {q}", site=s))

    # Keep only a small, deterministic list
    dedup: dict[str, SearchResult] = {}
    for r in out:
        dedup.setdefault(r.url, r)
    return list(dedup.values())[: max(3, len(ordered_sites) * 2)]


def search_stub(keywords: list[str], sites: list[str]) -> list[SearchResult]:
    """Backward-compatible stub.

    Kept for Stage A trace reproducibility.

    NOTE: Do not fabricate /search URLs for official Blizzard sites.
    """

    out: list[SearchResult] = []
    q = "+".join([k.strip().replace(" ", "+") for k in keywords[:3] if k.strip()])
    if not q:
        return []

    for s in sites[:3]:
        s2 = (s or "").strip().lower()
        if not s2 or s2 in {OFFICIAL_NEWS_HOST, OFFICIAL_FORUMS_HOST}:
            continue
        out.append(SearchResult(url=f"https://{s2}/search?q={q}", title=f"{s2} search: {q}", site=s2))
    return out
