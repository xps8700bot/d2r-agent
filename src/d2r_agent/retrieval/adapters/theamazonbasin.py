from __future__ import annotations

import time
from dataclasses import dataclass
import json
from typing import Any
from urllib.parse import quote

import requests

from d2r_agent.config import HTTP_MAX_RETRIES, HTTP_TIMEOUT_S
from d2r_agent.retrieval.cache import cache_get, cache_put
from d2r_agent.retrieval.extract import extract_snippets
from d2r_agent.schemas import EvidenceSnippet


BASIN_HOST = "theamazonbasin.com"
BASIN_BASE = "https://www.theamazonbasin.com"
# Basin wiki is hosted under /wiki/
BASIN_API = f"{BASIN_BASE}/wiki/api.php"
BASIN_REST_V1 = f"{BASIN_BASE}/wiki/rest.php/v1"
BASIN_PAGE_BASE = f"{BASIN_BASE}/wiki/index.php"


@dataclass
class BasinSearchHit:
    title: str
    url: str


def _get_text_with_cache(url: str, cache_dir: str) -> str:
    cached = cache_get(cache_dir, url)
    if cached is not None:
        return cached

    last_exc: Exception | None = None
    for i in range(HTTP_MAX_RETRIES + 1):
        try:
            r = requests.get(url, timeout=HTTP_TIMEOUT_S, headers={"User-Agent": "d2r-agent/0.2"})
            r.raise_for_status()
            txt = r.text
            cache_put(cache_dir, url, txt)
            return txt
        except Exception as e:
            last_exc = e
            time.sleep(0.5 * (i + 1))
    raise RuntimeError(f"basin request failed after retries: {url}: {last_exc}")


def basin_search_titles(query: str, cache_dir: str, limit: int = 5) -> list[BasinSearchHit]:
    """Search TheAmazonBasin via MediaWiki action API.

    Returns a list of page titles + canonical /wiki/ URLs.
    """
    # Use a cache key that is stable for this query
    url = (
        f"{BASIN_API}?action=query&list=search&format=json&srprop=&srlimit={int(limit)}"
        f"&srsearch={quote(query)}"
    )
    raw = _get_text_with_cache(url + "#json", cache_dir)
    data: dict[str, Any] = json.loads(raw)

    hits: list[BasinSearchHit] = []
    for item in (data.get("query", {}) or {}).get("search", []) or []:
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        page_url = f"{BASIN_PAGE_BASE}/{quote(title.replace(' ', '_'))}"
        hits.append(BasinSearchHit(title=title, url=page_url))
    return hits


def basin_fetch_page_html(title: str, cache_dir: str) -> tuple[str, str]:
    """Fetch page HTML.

    Basin's Parsoid HTML endpoint may be unavailable. We:
    1) Try REST HTML: /rest.php/v1/page/{title}/html
    2) Fallback to action=parse via api.php to get HTML fragment.

    Returns (source_url, html).
    """
    source_url = f"{BASIN_PAGE_BASE}/{quote(title.replace(' ', '_'))}"

    rest_html_url = f"{BASIN_REST_V1}/page/{quote(title)}/html"
    try:
        html = _get_text_with_cache(rest_html_url + "#html", cache_dir)
        # Some failures return JSON error; treat that as failure
        if html.lstrip().startswith("{") and "Unable to fetch Parsoid HTML" in html:
            raise RuntimeError("parsoid html unavailable")
        return source_url, html
    except Exception:
        # Use REST to warm/cache metadata (wikitext source) for debugging/replay
        _ = _get_text_with_cache(f"{BASIN_REST_V1}/page/{quote(title)}#json", cache_dir)

        parse_url = (
            f"{BASIN_API}?action=parse&format=json&prop=text&redirects=1"
            f"&page={quote(title)}"
        )
        raw = _get_text_with_cache(parse_url + "#json", cache_dir)
        data: dict[str, Any] = json.loads(raw)
        html_fragment = (((data.get("parse") or {}).get("text") or {}).get("*") or "").strip()
        if not html_fragment:
            raise RuntimeError(f"empty parse html for {title}")
        # Wrap to make BeautifulSoup happier
        html = f"<html><body><h1>{title}</h1>{html_fragment}</body></html>"
        return source_url, html


def basin_extract_evidence(title: str, cache_dir: str, max_snippets: int = 3) -> list[EvidenceSnippet]:
    source_url, html = basin_fetch_page_html(title, cache_dir)
    snippets = extract_snippets(html, source_url=source_url, source_site=BASIN_HOST, max_snippets=max_snippets)
    # If extractor couldn't find h1, make sure title is present
    for s in snippets:
        if not s.title_path:
            s.title_path = [title]
    return snippets
