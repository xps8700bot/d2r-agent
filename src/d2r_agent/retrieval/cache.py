from __future__ import annotations

import hashlib
from pathlib import Path


def cache_key(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def cache_get(cache_dir: str, url: str) -> str | None:
    p = Path(cache_dir) / f"{cache_key(url)}.html"
    if p.exists():
        return p.read_text(encoding="utf-8", errors="ignore")
    return None


def cache_put(cache_dir: str, url: str, html: str) -> Path:
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    p = Path(cache_dir) / f"{cache_key(url)}.html"
    p.write_text(html, encoding="utf-8")
    return p
