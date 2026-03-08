from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from d2r_agent.retrieval.cache import cache_get, cache_put
from d2r_agent.retrieval.fetch import fetch_url
from d2r_agent.schemas import EvidenceSnippet


FORUMS_HOST = "us.forums.blizzard.com"


@dataclass
class ForumsThread:
    url: str


def forums_extract_evidence(
    thread_url: str,
    keywords: Optional[list[str]] = None,
    max_snippets: int = 2,
    cache_dir: Optional[str] = None,
) -> list[EvidenceSnippet]:
    """Official Blizzard D2R forums adapter.

    Constraints (intentionally strict):
    - Only fetch + extract from a *known thread URL* on us.forums.blizzard.com.

    This keeps the agent within the official-domain whitelist and avoids broad crawling.

    Caching:
    - If cache_dir is provided, fetched HTML is cached by URL.

    Extraction:
    - Very rough HTML->text collapse, then keyword window snippets.
    """

    u = urlparse(thread_url)
    if u.netloc != FORUMS_HOST:
        raise ValueError(f"not an official forums URL: {thread_url}")

    html: str | None = None
    if cache_dir:
        html = cache_get(cache_dir, thread_url)

    if html is None:
        fr = fetch_url(thread_url)
        if fr.status >= 400:
            raise RuntimeError(f"fetch failed: {thread_url} status={fr.status}")
        html = fr.text
        if cache_dir:
            cache_put(cache_dir, thread_url, html)

    text = html
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    kws = [k.strip().lower() for k in (keywords or []) if k and k.strip()]
    if not kws:
        kws = ["season", "ladder", "disabled", "start"]

    low = text.lower()
    snippets: list[EvidenceSnippet] = []
    for kw in kws[:8]:
        idx = low.find(kw)
        if idx < 0:
            continue
        start = max(0, idx - 120)
        end = min(len(text), idx + 220)
        snippets.append(
            EvidenceSnippet(
                source_url=thread_url,
                source_site=u.netloc,
                title_path=["Official Forums"],
                snippet=text[start:end].strip(),
                evidence_source_type="extract",
            )
        )
        if len(snippets) >= max_snippets:
            break

    if not snippets:
        snippets.append(
            EvidenceSnippet(
                source_url=thread_url,
                source_site=u.netloc,
                title_path=["Official Forums"],
                snippet="(stub) Fetched official forum thread but did not find keyword hits; please open the link to verify.",
                evidence_source_type="stub",
            )
        )

    return snippets
