from __future__ import annotations

import argparse
from urllib.parse import urljoin, urlparse

import requests
import yaml
from bs4 import BeautifulSoup


def discover_internal_links(url: str) -> list[str]:
    r = requests.get(url, timeout=20, headers={"User-Agent": "d2r-agent/0.2"})
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")
    base_host = (urlparse(url).hostname or "").lower()

    links: set[str] = set()
    for a in soup.find_all("a"):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#"):
            continue
        full = urljoin(url, href)
        pu = urlparse(full)
        if (pu.hostname or "").lower() != base_host:
            continue
        if pu.scheme not in ("http", "https"):
            continue
        # Normalize
        norm = f"{pu.scheme}://{pu.hostname}{pu.path}".rstrip("/")
        if not norm:
            continue
        links.add(norm)

    # Warlock-specific curation (keep it simple; user can edit yaml afterwards)
    curated = [
        u
        for u in sorted(links)
        if any(x in u for x in ["/warlock", "-warlock", "warlock-"])
        and any(x in u for x in ["/guides/", "/resources/"])
    ]
    return curated


def main() -> int:
    ap = argparse.ArgumentParser(description="Discover Maxroll internal seed URLs from an overview page")
    ap.add_argument("overview_url", help="e.g. https://maxroll.gg/d2/resources/warlock-overview")
    ap.add_argument("--out", default="data/seed_urls.yaml", help="output yaml path")
    args = ap.parse_args()

    seeds = discover_internal_links(args.overview_url)

    payload = {
        "maxroll": {
            "overview": args.overview_url,
            "seed_urls": seeds,
        }
    }

    with open(args.out, "w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=True)

    print(f"wrote {args.out} ({len(seeds)} urls)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
