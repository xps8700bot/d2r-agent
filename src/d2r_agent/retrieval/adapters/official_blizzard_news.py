from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from d2r_agent.retrieval.fetch import fetch_url
from d2r_agent.schemas import EvidenceSnippet


NEWS_HOST = "news.blizzard.com"


def _clean_text(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s


def _page_title(soup: BeautifulSoup) -> str:
    og = soup.find("meta", attrs={"property": "og:title"})
    if og and og.get("content"):
        return _clean_text(str(og.get("content")))

    t = soup.find("title")
    if t:
        return _clean_text(t.get_text(" ", strip=True))

    h1 = soup.find("h1")
    if h1:
        return _clean_text(h1.get_text(" ", strip=True))

    return "Blizzard News"


def _iter_sections(soup: BeautifulSoup):
    """Yield (level:int, heading_text:str, section_text:str) for h2/h3/h4 sections.

    We walk headings in document order and collect following sibling text until the next
    heading of same-or-higher level.
    """

    headings = soup.find_all(["h2", "h3", "h4"])
    for i, h in enumerate(headings):
        level = int(h.name[1])
        heading_text = _clean_text(h.get_text(" ", strip=True))
        if not heading_text:
            continue

        # Collect all text until next heading of level <= current level
        chunks: list[str] = []
        node = h
        while True:
            node = node.find_next_sibling()
            if node is None:
                break
            if getattr(node, "name", None) in ("h2", "h3", "h4"):
                next_level = int(node.name[1])
                if next_level <= level:
                    break
            # Ignore scripts/styles
            if getattr(node, "name", None) in ("script", "style"):
                continue
            txt = _clean_text(node.get_text(" ", strip=True) if hasattr(node, "get_text") else str(node))
            if txt:
                chunks.append(txt)
            # Prevent runaway on very long pages
            if sum(len(c) for c in chunks) > 5000:
                break

        section_text = _clean_text(" ".join(chunks))
        if section_text:
            yield level, heading_text, section_text


def news_extract_evidence(article_url: str, keywords: list[str] | None = None, max_snippets: int = 3) -> list[EvidenceSnippet]:
    """Blizzard News adapter.

    - Fetches a Blizzard News article.
    - Extracts evidence from H2/H3/H4 sections with a stable `title_path`.

    `title_path` format:
      [<page_title>, <h2>, <h3>, <h4>]
    (only including the headings that exist for the chosen section).
    """

    u = urlparse(article_url)
    if u.netloc != NEWS_HOST:
        raise ValueError(f"not a Blizzard News URL: {article_url}")

    fr = fetch_url(article_url)
    if fr.status >= 400:
        raise RuntimeError(f"fetch failed: {article_url} status={fr.status}")

    soup = BeautifulSoup(fr.text, "lxml")
    page_title = _page_title(soup)

    kws = [k.strip().lower() for k in (keywords or []) if k and k.strip()]
    if not kws:
        kws = ["season", "ladder", "patch", "resurrected", "diablo ii"]

    # Walk sections and pick those with keyword hits first.
    picked: list[EvidenceSnippet] = []

    # Track current heading hierarchy for stable title paths.
    cur_h2 = None
    cur_h3 = None

    for level, htext, section_text in _iter_sections(soup):
        low = section_text.lower()

        if level == 2:
            cur_h2, cur_h3 = htext, None
            title_path = [page_title, htext]
        elif level == 3:
            cur_h3 = htext
            title_path = [page_title] + ([cur_h2] if cur_h2 else []) + [htext]
        else:  # h4
            title_path = [page_title] + ([cur_h2] if cur_h2 else []) + ([cur_h3] if cur_h3 else []) + [htext]

        hit_kw = next((kw for kw in kws if kw in low), None)
        if not hit_kw:
            continue

        snippet = section_text[:420]
        picked.append(
            EvidenceSnippet(
                source_url=article_url,
                source_site=u.netloc,
                title_path=[t for t in title_path if t],
                snippet=snippet,
                evidence_source_type="extract",
            )
        )
        if len(picked) >= max_snippets:
            return picked

    # Fallback: if no keyword hits, return the first non-empty section(s)
    if not picked:
        cur_h2 = cur_h3 = None
        for level, htext, section_text in _iter_sections(soup):
            if level == 2:
                cur_h2, cur_h3 = htext, None
                title_path = [page_title, htext]
            elif level == 3:
                cur_h3 = htext
                title_path = [page_title] + ([cur_h2] if cur_h2 else []) + [htext]
            else:
                title_path = [page_title] + ([cur_h2] if cur_h2 else []) + ([cur_h3] if cur_h3 else []) + [htext]

            picked.append(
                EvidenceSnippet(
                    source_url=article_url,
                    source_site=u.netloc,
                    title_path=[t for t in title_path if t],
                    snippet=section_text[:420],
                    evidence_source_type="extract",
                )
            )
            if len(picked) >= min(1, max_snippets):
                break

    if not picked:
        picked.append(
            EvidenceSnippet(
                source_url=article_url,
                source_site=u.netloc,
                title_path=[page_title],
                snippet="(stub) Fetched Blizzard News article but did not find extractable H2/H3/H4 sections; please open the link to verify.",
                evidence_source_type="stub",
            )
        )

    return picked
