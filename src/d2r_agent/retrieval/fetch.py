from __future__ import annotations

import time
from dataclasses import dataclass

import requests

from d2r_agent.config import HTTP_MAX_RETRIES, HTTP_TIMEOUT_S


@dataclass
class FetchResult:
    url: str
    status: int
    text: str
    content_type: str | None = None


def fetch_url(url: str, timeout_s: int = HTTP_TIMEOUT_S, max_retries: int = HTTP_MAX_RETRIES) -> FetchResult:
    """阶段 B 会用到。MVP 保留实现但默认不在主流程里抓取真实页面。

    这里做了最基础的超时/重试；解析与抽取在 extract.py。
    """
    last_exc: Exception | None = None
    for i in range(max_retries + 1):
        try:
            r = requests.get(url, timeout=timeout_s, headers={"User-Agent": "d2r-agent/0.1"})
            return FetchResult(
                url=url,
                status=r.status_code,
                text=r.text,
                content_type=r.headers.get("content-type"),
            )
        except Exception as e:
            last_exc = e
            time.sleep(0.5 * (i + 1))
    raise RuntimeError(f"fetch failed after retries: {url}: {last_exc}")
