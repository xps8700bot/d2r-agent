from __future__ import annotations

from urllib.parse import urlparse


def is_whitelisted(url: str, whitelist_domains: list[str]) -> bool:
    host = urlparse(url).netloc.lower()
    if not host:
        return False
    return any(host == d or host.endswith("." + d) for d in whitelist_domains)
