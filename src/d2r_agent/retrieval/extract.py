from __future__ import annotations

from bs4 import BeautifulSoup

from d2r_agent.schemas import EvidenceSnippet


def extract_snippets(html: str, source_url: str, source_site: str, max_snippets: int = 3) -> list[EvidenceSnippet]:
    """阶段 B：HTML → 证据片段（带标题路径/section）。

    MVP：非常粗糙，只抽取前几个段落文本。
    """
    soup = BeautifulSoup(html, "lxml")
    # 尝试抓取标题路径
    h1 = soup.find("h1")
    title_path = [h1.get_text(strip=True)] if h1 else []

    snippets: list[EvidenceSnippet] = []

    # Pass 1: paragraphs / list items
    for p in soup.find_all(["p", "li"], limit=80):
        t = p.get_text(" ", strip=True)
        if not t or len(t) < 40:
            continue
        snippets.append(
            EvidenceSnippet(
                source_url=source_url,
                source_site=source_site,
                title_path=title_path,
                snippet=t[:280],
            )
        )
        if len(snippets) >= max_snippets:
            return snippets

    # Pass 2: MediaWiki pages often encode key facts in tables (runewords, recipes)
    for cell in soup.find_all(["th", "td"], limit=200):
        t = cell.get_text(" ", strip=True)
        if not t or len(t) < 40:
            continue
        # Skip nav boxes / noisy repeats
        if "Retrieved from" in t or "navigation" in t.lower():
            continue
        words = [w for w in t.split() if w]
        if words:
            caps = sum(1 for w in words if w[:1].isupper())
            if caps / max(1, len(words)) > 0.75 and len(words) > 12:
                # Likely a navbox / index list rather than a fact cell
                continue
        snippets.append(
            EvidenceSnippet(
                source_url=source_url,
                source_site=source_site,
                title_path=title_path,
                snippet=t[:280],
            )
        )
        if len(snippets) >= max_snippets:
            break

    return snippets
