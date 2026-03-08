from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from d2r_agent.config import HTTP_MAX_RETRIES, HTTP_TIMEOUT_S
from d2r_agent.retrieval.cache import cache_get, cache_put


MAXROLL_HOSTS = {"maxroll.gg", "www.maxroll.gg"}


@dataclass
class MaxrollSection:
    title_path: list[str]
    text: str


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
    raise RuntimeError(f"maxroll request failed after retries: {url}: {last_exc}")


def extract_maxroll_sections(html: str) -> list[MaxrollSection]:
    """Extract structured, quotable sections from Maxroll HTML.

    Goal: strategy nuggets (headings + the following paragraphs/lists).
    This intentionally ignores build planner tables and dynamic widgets.
    """

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    h1 = soup.find("h1")
    page_title = h1.get_text(" ", strip=True) if h1 else ""

    # Try to focus on main content (Maxroll pages often use <main>).
    root = soup.find("main") or soup.body or soup

    sections: list[MaxrollSection] = []

    current_path: list[str] = [page_title] if page_title else []
    buf: list[str] = []

    def flush():
        nonlocal buf
        txt = " ".join([b.strip() for b in buf if b.strip()])
        buf = []
        if not txt:
            return
        # Drop tiny fragments
        if len(txt) < 60:
            return
        sections.append(MaxrollSection(title_path=[p for p in current_path if p], text=txt))

    for el in root.find_all(["h2", "h3", "p", "li"], limit=2500):
        if el.name in ("h2", "h3"):
            flush()
            heading = el.get_text(" ", strip=True)
            if heading:
                # Keep h1 as prefix
                if page_title:
                    current_path = [page_title, heading]
                else:
                    current_path = [heading]
            continue

        t = el.get_text(" ", strip=True)
        if not t:
            continue
        # Skip obvious nav/footer noise
        low = t.lower()
        if "cookie" in low and "privacy" in low:
            continue
        if "subscribe" in low and "newsletter" in low:
            continue

        buf.append(t)
        if sum(len(x) for x in buf) > 900:
            flush()

    flush()

    # Deduplicate near-identical sections
    seen: set[str] = set()
    out: list[MaxrollSection] = []
    for s in sections:
        key = ("|".join(s.title_path) + "::" + s.text[:120]).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)

    return out


def fetch_and_extract(url: str, cache_dir: str) -> tuple[str, list[MaxrollSection]]:
    host = (urlparse(url).hostname or "").lower()
    if host not in MAXROLL_HOSTS:
        raise ValueError(f"not a maxroll url: {url}")

    html = _get_text_with_cache(url, cache_dir)
    return url, extract_maxroll_sections(html)
