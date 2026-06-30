"""A polite HTTP client: identifies itself, rate-limits, retries, caches, and
honours robots.txt. Used for all disclosure scraping.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from urllib import robotparser
from urllib.parse import urlencode, urlparse

import requests

DEFAULT_UA = (
    "stock-prices-disclosures/1.0 (civic-transparency research; "
    "contact via repository owner)"
)


class PoliteClient:
    def __init__(
        self,
        user_agent: str = DEFAULT_UA,
        delay: float = 1.5,
        cache_dir: str = ".cache/disclosures",
        respect_robots: bool = True,
        timeout: int = 30,
    ):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self.user_agent = user_agent
        self.delay = delay
        self.timeout = timeout
        self.respect_robots = respect_robots
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._last_request = 0.0
        self._robots: dict[str, robotparser.RobotFileParser | None] = {}

    # -- robots -------------------------------------------------------------
    def _robot_ok(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parsed = urlparse(url)
        host = f"{parsed.scheme}://{parsed.netloc}"
        if host not in self._robots:
            rp = robotparser.RobotFileParser()
            rp.set_url(host + "/robots.txt")
            try:
                rp.read()
            except Exception:
                rp = None  # robots unreadable -> don't block, just be polite
            self._robots[host] = rp
        rp = self._robots[host]
        return True if rp is None else rp.can_fetch(self.user_agent, url)

    # -- cache --------------------------------------------------------------
    def _cache_path(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
        return self.cache_dir / f"{digest}.html"

    # -- fetch --------------------------------------------------------------
    def get(self, url: str, params: dict | None = None, refresh: bool = False) -> str:
        full = url
        if params:
            full = url + ("&" if "?" in url else "?") + urlencode(params)

        cache_path = self._cache_path(full)
        if not refresh and cache_path.exists():
            return cache_path.read_text(encoding="utf-8")

        if not self._robot_ok(full):
            raise PermissionError(f"robots.txt disallows fetching {full}")

        wait = self.delay - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)

        text = self._request_with_retry(full)
        self._last_request = time.monotonic()
        cache_path.write_text(text, encoding="utf-8")
        return text

    def _request_with_retry(self, url: str, retries: int = 3) -> str:
        resp = None
        for attempt in range(retries):
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2.0 ** attempt)
                continue
            break
        assert resp is not None
        resp.raise_for_status()
        # apparent_encoding fixes pages whose declared charset is wrong
        resp.encoding = resp.apparent_encoding or resp.encoding
        return resp.text
