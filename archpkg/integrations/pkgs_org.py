"""
pkgs_org.py
A resilient wrapper for searching pkgs.org (unofficial JSON endpoint + HTML fallback).

Usage:
    client = PkgsOrgClient(cache_dir="~/.cache/archpkg-helper", ttl=3600)
    results = client.search("spotify", distro="ubuntu", limit=10)
    # results is a list of dicts with keys: name, version, distro, repo, url, summary
"""

from __future__ import annotations
import os
import time
import json
import hashlib
import logging
from typing import List, Optional, Dict, Any
from urllib.parse import quote_plus, urljoin

import requests

# Optional dependency for HTML parsing
try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None  # fallback will error with a nice message if needed

# Basic logging
logger = logging.getLogger("pkgs_org")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("[pkgs.org] %(levelname)s: %(message)s"))
    logger.addHandler(ch)

# Default endpoints (undocumented/unofficial)
JSON_SEARCH_URL = "https://api.pkgs.org/v1/search?q={q}"
HTML_SEARCH_URL = "https://pkgs.org/search/?q={q}"     # distro can be appended as &on=<distro>

# Default request settings
DEFAULT_TIMEOUT = 10.0          # seconds
RETRY_COUNT = 2
RETRY_BACKOFF = 1.0            # seconds between retries
MIN_REQUEST_INTERVAL = 0.5     # seconds - polite throttling

# Cache settings
DEFAULT_CACHE_DIR = os.path.expanduser("~/.cache/archpkg-helper")
DEFAULT_CACHE_FILE = os.path.join(DEFAULT_CACHE_DIR, "pkgs_org_cache.json")


def _ensure_cache_dir(path: str) -> None:
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)


def _hash_key(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class DiskCache:
    """A tiny file-backed JSON cache with TTL. Not highly concurrent; intended for CLI usage."""
    def __init__(self, path: str = DEFAULT_CACHE_FILE):
        self.path = os.path.expanduser(path)
        _ensure_cache_dir(self.path)
        self._load()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except Exception:
            self._data = {}

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        rec = self._data.get(key)
        if not rec:
            return None
        now = time.time()
        if rec.get("expires_at", 0) < now:
            # expired
            self._data.pop(key, None)
            self._save()
            return None
        return rec.get("value")

    def set(self, key: str, value: Any, ttl: int):
        rec = {"value": value, "expires_at": time.time() + ttl}
        self._data[key] = rec
        self._save()


class PkgsOrgClient:
    def __init__(
        self,
        cache_file: str = DEFAULT_CACHE_FILE,
        ttl: int = 3600,
        user_agent: str = "archpkg-helper/1.0 (+https://github.com/AdmGenSameer/archpkg-helper)",
        min_request_interval: float = MIN_REQUEST_INTERVAL,
    ):
        self.cache = DiskCache(cache_file)
        self.ttl = ttl
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        adapter = requests.adapters.HTTPAdapter(max_retries=RETRY_COUNT)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self._last_request = 0.0
        self._min_request_interval = float(min_request_interval)

    def _throttle(self):
        delta = time.time() - self._last_request
        if delta < self._min_request_interval:
            time.sleep(self._min_request_interval - delta)

    def _get_cached(self, key: str):
        return self.cache.get(key)

    def _set_cached(self, key: str, value: Any):
        self.cache.set(key, value, ttl=self.ttl)

    def _cache_key_for_search(self, query: str, distro: Optional[str], limit: int):
        key = f"search:{distro or 'any'}:{limit}:{query}"
        return _hash_key(key)

    def search(self, query: str, distro: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search pkgs.org for 'query'. Returns a list of dicts:
          { name, version, distro, repo, url, summary }
        """
        cache_key = self._cache_key_for_search(query, distro, limit)
        cached = self._get_cached(cache_key)
        if cached is not None:
            logger.debug("Cache hit for query=%s distro=%s", query, distro)
            return cached

        # Try JSON endpoint first (fast)
        try:
            results = self._search_json(query, distro=distro, limit=limit)
            if results:
                self._set_cached(cache_key, results)
                return results
        except Exception as e:
            logger.debug("JSON search failed: %s", e)

        # Fallback to HTML scraping
        results = self._search_html(query, distro=distro, limit=limit)
        self._set_cached(cache_key, results)
        return results

    def _search_json(self, query: str, distro: Optional[str], limit: int) -> List[Dict[str, Any]]:
        """
        Use the unofficial JSON endpoint:
          https://api.pkgs.org/v1/search?q=...
        Note: undocumented; may change.
        """
        self._throttle()
        url = JSON_SEARCH_URL.format(q=quote_plus(query))
        # Some sites accept distro hint via query param 'on', but JSON endpoint may not support it.
        logger.debug("JSON search %s", url)
        resp = self.session.get(url, timeout=DEFAULT_TIMEOUT)
        self._last_request = time.time()
        if resp.status_code != 200:
            raise RuntimeError(f"JSON endpoint returned status {resp.status_code}")
        data = resp.json()
        # The structure of the JSON is unofficial; we'll try to robustly extract results.
        results = []
        items = data.get("results") or data.get("packages") or data.get("data") or []
        for it in items[:limit]:
            try:
                # best-effort extraction
                name = it.get("name") or it.get("pkg_name") or it.get("package")
                version = it.get("version") or it.get("pkg_ver") or it.get("ver") or ""
                repo = it.get("repository") or it.get("repo") or it.get("package_repository") or ""
                url = it.get("package_url") or it.get("url") or it.get("link") or ""
                summary = it.get("summary") or it.get("description") or ""
                distro_hint = (it.get("distro") or it.get("os") or None)
                item = {"name": name, "version": version, "repo": repo, "url": url, "summary": summary, "distro": distro_hint}
                results.append(item)
            except Exception:
                continue
        return results

    def _search_html(self, query: str, distro: Optional[str], limit: int) -> List[Dict[str, Any]]:
        """
        Scrape pkgs.org search page as fallback.
        Example URL: https://pkgs.org/search/?q=<query>&on=ubuntu
        """
        if BeautifulSoup is None:
            raise RuntimeError("BeautifulSoup is required for HTML fallback. Install 'beautifulsoup4'.")

        self._throttle()
        q = quote_plus(query)
        url = HTML_SEARCH_URL.format(q=q)
        if distro:
            url = url + "&on=" + quote_plus(distro)
        logger.debug("HTML search %s", url)
        resp = self.session.get(url, timeout=DEFAULT_TIMEOUT)
        self._last_request = time.time()
        if resp.status_code != 200:
            raise RuntimeError(f"HTML search returned status {resp.status_code}")

        soup = BeautifulSoup(resp.content, "html.parser")
        results: List[Dict[str, Any]] = []

        # pkgs.org search result HTML structure (best-effort parsing)
        # Each result often appears as <div class="package"> or <div class="row"> with <a href="/.../pkg.html">Name</a>
        # We'll search for links that look like package pages (contain '/download/' or end with '.html')
        # and try to extract repo/distro text near them.
        anchors = soup.find_all("a", href=True)
        seen = set()
        for a in anchors:
            href = a["href"]
            if ("/download/" in href) or href.endswith(".html") or "/package/" in href:
                name_text = a.get_text(strip=True)
                if not name_text:
                    continue
                # build absolute URL
                package_url = urljoin("https://pkgs.org", href)
                key = (name_text, package_url)
                if key in seen:
                    continue
                seen.add(key)

                # attempt to find a repository/distro string nearby
                parent = a.parent
                summary = ""
                repo = ""
                distro_hint = None
                # look for small tags or spans
                small = parent.find("small") if parent else None
                if small:
                    summary = small.get_text(" ", strip=True)

                # sometimes repo/distro are in the same row; search siblings for a '.repo' or 'td' with distro text
                sib = parent.find_next_sibling()
                if sib:
                    repo = sib.get_text(" ", strip=True)

                results.append({"name": name_text, "version": "", "repo": repo, "url": package_url, "summary": summary, "distro": distro_hint})
                if len(results) >= limit:
                    break

        # If nothing found, as last resort, try more structured table parsing
        if not results:
            # look for tables with search results
            tables = soup.find_all("table")
            for t in tables:
                for row in t.find_all("tr"):
                    cols = row.find_all("td")
                    if len(cols) >= 2:
                        link = cols[0].find("a", href=True)
                        if link:
                            name = link.get_text(strip=True)
                            url = urljoin("https://pkgs.org", link["href"])
                            repo = cols[1].get_text(" ", strip=True)
                            results.append({"name": name, "version": "", "repo": repo, "url": url, "summary": "", "distro": None})
                    if len(results) >= limit:
                        break
                if len(results) >= limit:
                    break

        return results

    def get_package_page(self, package_url: str) -> Dict[str, Any]:
        """
        Fetch and parse a package detail page on pkgs.org to extract more fields.
        Returns a dict with at least: name, version, repo, distro, description, url
        """
        self._throttle()
        logger.debug("Fetching package page %s", package_url)
        resp = self.session.get(package_url, timeout=DEFAULT_TIMEOUT)
        self._last_request = time.time()
        if resp.status_code != 200:
            raise RuntimeError(f"Package page returned {resp.status_code}")

        if BeautifulSoup is None:
            raise RuntimeError("BeautifulSoup is required to parse package pages.")

        soup = BeautifulSoup(resp.content, "html.parser")
        # name usually in <h1>
        name_tag = soup.find("h1")
        name = name_tag.get_text(strip=True) if name_tag else ""
        # try find a short description
        desc = ""
        desc_tag = soup.find("p", class_="lead") or soup.find("div", class_="desc") or None
        if desc_tag:
            desc = desc_tag.get_text(" ", strip=True)

        # repo and distro can be in breadcrumbs or small tags
        repo = ""
        distro = ""
        breadcrumb = soup.find("ol", class_="breadcrumb")
        if breadcrumb:
            crumb_text = breadcrumb.get_text(" / ", strip=True)
            distro = crumb_text

        # version may be near the name or in a label
        version = ""
        ver_tag = soup.find(lambda t: t.name in ("span", "small") and "version" in (t.get("class") or []))
        if ver_tag:
            version = ver_tag.get_text(" ", strip=True)

        return {"name": name, "version": version, "repo": repo, "distro": distro, "description": desc, "url": package_url}


# Small self-test when invoked directly
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="pkgs.org client test")
    parser.add_argument("query", nargs="?", default="spotify")
    parser.add_argument("--distro", default=None)
    parser.add_argument("--limit", type=int, default=6)
    args = parser.parse_args()
    c = PkgsOrgClient()
    try:
        res = c.search(args.query, distro=args.distro, limit=args.limit)
        print(json.dumps(res, indent=2, ensure_ascii=False))
    except Exception as e:
        print("Error:", e)
        raise
