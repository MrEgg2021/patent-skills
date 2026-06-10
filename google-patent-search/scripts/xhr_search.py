#!/usr/bin/env python3
"""Google Patents XHR/Query endpoint search.

Uses the internal ``/xhr/query`` endpoint that Google Patents' frontend
calls when a user submits a search.  This returns structured JSON
directly — no browser / JS rendering required.

Key advantages over the Playwright-based search page:
  * country:CN works (not blocked like on the search page).
  * Chinese patents appear in results (machine-translated & indexed).
  * Pure HTTP request — fast, no GUI, headless-friendly.
  * Structured JSON response — no fragile HTML parsing.

Rate-limiting:  Google returns HTTP 503 after ~5 rapid requests.
Callers should wait ≥30 s between searches or implement retry logic.
"""

from __future__ import annotations

import json
import re
import sys
import time
import argparse
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

XHR_BASE = "https://patents.google.com/xhr/query"
DEFAULT_USER_AGENT = "patent-search-tool/1.0"
REQUEST_TIMEOUT = 30          # seconds
RETRY_DELAY = 120             # seconds to wait on 503 before retrying
MAX_RETRIES = 1               # how many 503 retries before giving up
MIN_INTERVAL = 30             # minimum seconds between consecutive requests

_last_request_time: float = 0.0   # module-level throttle

# Fields we extract from each patent result
PATENT_FIELDS = (
    "publication_number", "country", "title", "snippet",
    "priority_date", "filing_date", "grant_date", "publication_date",
    "inventor", "assignee", "pdf", "patent_id", "language",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_html_tags(text: str) -> str:
    """Remove <b>…</b> and other HTML tags from Google's highlight markup."""
    return re.sub(r"<[^>]+>", "", text)


def _extract_country(pub_number: str) -> str:
    """Derive a 2-letter country code from a publication number like 'CN107390684B'."""
    if not pub_number:
        return ""
    # Patent ID format is "patent/CN107390684B/zh" → country = "CN"
    m = re.match(r"^([A-Z]{2})", pub_number)
    return m.group(1) if m else ""


def _build_xhr_url(query: str, page: int = 0) -> str:
    """Build the full XHR/query URL from a Google Patents query string.

    Parameters
    ----------
    query:
        A Google Patents search query, e.g. ``"path planning" AND robot country:CN``.
    page:
        Zero-based page number (each page ~10 results by default).

    Returns
    -------
    str  The fully-constructed URL.
    """
    encoded_q = urllib.parse.quote(query)
    url = f"{XHR_BASE}?url=q%3D{encoded_q}"
    if page > 0:
        url += f"&page={page}"
    return url


# ---------------------------------------------------------------------------
# Core search
# ---------------------------------------------------------------------------

def xhr_search(
    query: str,
    *,
    proxy_url: str | None = None,
    page: int = 0,
    timeout: int = REQUEST_TIMEOUT,
    max_retries: int = MAX_RETRIES,
    retry_delay: int = RETRY_DELAY,
    min_interval: float = MIN_INTERVAL,
    user_agent: str = DEFAULT_USER_AGENT,
) -> dict[str, Any]:
    """Search Google Patents via the ``/xhr/query`` endpoint.

    Parameters
    ----------
    query:
        Google Patents query string (supports AND/OR/country: etc.).
    proxy_url:
        HTTPS proxy, e.g. ``"http://127.0.0.1:7897"``.  Required in China.
    page:
        Zero-based page number.
    timeout:
        Per-request timeout in seconds.
    max_retries:
        How many times to retry on HTTP 503.
    retry_delay:
        Seconds to wait before retrying on 503.
    min_interval:
        Minimum seconds between consecutive requests (throttle).
    user_agent:
        Value for the User-Agent header.

    Returns
    -------
    dict with keys ``total_num_results``, ``patents``, ``query``, ``page``,
    ``timestamp``, ``xhr_url``.
    """
    global _last_request_time

    url = _build_xhr_url(query, page)
    headers = {"User-Agent": user_agent}

    # Build opener (with or without proxy)
    if proxy_url:
        proxy_handler = urllib.request.ProxyHandler({"https": proxy_url})
        opener = urllib.request.build_opener(proxy_handler)
    else:
        opener = urllib.request.build_opener()

    # Throttle
    elapsed = time.time() - _last_request_time
    if elapsed < min_interval:
        wait = min_interval - elapsed
        print(f"  [xhr_search] Throttling: waiting {wait:.0f}s …")
        time.sleep(wait)

    # Request with 503 retry
    data: dict[str, Any] | None = None
    last_error: Exception | None = None
    for attempt in range(1 + max_retries):
        try:
            _last_request_time = time.time()
            req = urllib.request.Request(url, headers=headers)
            with opener.open(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                data = json.loads(raw)
                break
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 503:
                print(f"  [xhr_search] HTTP 503 (rate-limited) on attempt {attempt + 1}/{1 + max_retries}")
                if attempt < max_retries:
                    print(f"  [xhr_search] Retrying in {retry_delay}s …")
                    time.sleep(retry_delay)
                continue
            raise
        except (urllib.error.URLError, OSError) as exc:
            last_error = exc
            print(f"  [xhr_search] Network error: {exc}")
            if attempt < max_retries:
                time.sleep(retry_delay)
                continue
            raise

    if data is None:
        raise RuntimeError(f"xhr_search failed after {1 + max_retries} attempts. Last error: {last_error}")

    # Parse results
    patents = _parse_xhr_response(data)

    return {
        "total_num_results": data.get("results", {}).get("total_num_results", 0),
        "total_num_pages": data.get("results", {}).get("total_num_pages", 0),
        "patents": patents,
        "query": query,
        "page": page,
        "xhr_url": url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _parse_xhr_response(data: dict) -> list[dict[str, Any]]:
    """Extract a flat list of patent dicts from the XHR JSON response."""
    patents: list[dict[str, Any]] = []
    for cluster in data.get("results", {}).get("cluster", []):
        for result in cluster.get("result", []):
            p = result.get("patent", {})
            pub_num = p.get("publication_number", "")
            country = _extract_country(pub_num)

            # Also extract country from patent_id if pub_num is missing
            patent_id = result.get("id", "")
            if not country and patent_id:
                m = re.search(r"patent/([A-Z]{2})", patent_id)
                if m:
                    country = m.group(1)

            patents.append({
                "publication_number": pub_num,
                "country": country,
                "title": _strip_html_tags(p.get("title", "")),
                "snippet": _strip_html_tags(p.get("snippet", "")),
                "priority_date": p.get("priority_date", ""),
                "filing_date": p.get("filing_date", ""),
                "grant_date": p.get("grant_date", ""),
                "publication_date": p.get("publication_date", ""),
                "inventor": p.get("inventor", ""),
                "assignee": p.get("assignee", ""),
                "pdf": p.get("pdf", ""),
                "patent_id": patent_id,
                "language": p.get("language", ""),
                # family metadata for CN detection
                "family_countries": [
                    cs.get("country_code", "")
                    for cs in p.get("family_metadata", {})
                              .get("aggregated", {})
                              .get("country_status", [])
                ],
                "has_cn_family": any(
                    cs.get("country_code") == "CN"
                    for cs in p.get("family_metadata", {})
                              .get("aggregated", {})
                              .get("country_status", [])
                ),
            })
    return patents


# ---------------------------------------------------------------------------
# Convenience: search with country filter
# ---------------------------------------------------------------------------

def xhr_search_cn(
    query: str,
    *,
    proxy_url: str | None = None,
    mode: str = "filter",
    page: int = 0,
    **kwargs,
) -> dict[str, Any]:
    """Search for Chinese patents via the XHR endpoint.

    Two modes:

    ``filter`` (default, recommended)
        Append ``country:CN`` to the query.  This is handled server-side
        and has been verified to work on the XHR endpoint (unlike the
        search page where ``country:CN`` triggers ERR_CONNECTION_CLOSED).

    ``post``
        Run the query without ``country:CN``, then filter results where
        ``country == "CN"``.  Fallback if ``country:CN`` ever stops
        working on the XHR endpoint.

    Parameters
    ----------
    query:
        Google Patents query (English keywords recommended).
    mode:
        ``"filter"`` to use country:CN syntax; ``"post"`` to post-filter.
    """
    if mode == "filter":
        # Append country:CN if not already present
        if "country:CN" not in query.upper() and "COUNTRY:CN" not in query:
            query = f"{query} country:CN"
    result = xhr_search(query, proxy_url=proxy_url, page=page, **kwargs)
    if mode == "post":
        result["patents"] = [p for p in result["patents"] if p.get("country") == "CN"]
    return result


# ---------------------------------------------------------------------------
# Multi-strategy search (integrates with search_intelligence query sets)
# ---------------------------------------------------------------------------

def xhr_multi_search(
    query_sets: list[dict[str, str]],
    *,
    proxy_url: str | None = None,
    max_results_per_set: int = 50,
    cn_only: bool = False,
    cn_mode: str = "filter",
    **kwargs,
) -> dict[str, Any]:
    """Run multiple query strategies via the XHR endpoint and merge results.

    Parameters
    ----------
    query_sets:
        List of dicts with keys ``strategy_name`` and ``query``.
    cn_only:
        If True, filter results to CN patents only.
    cn_mode:
        How to filter for CN patents (``"filter"`` or ``"post"``).
    """
    all_patents: list[dict[str, Any]] = []
    seen_pub_nums: set[str] = set()
    per_strategy_counts: dict[str, int] = {}

    for qs in query_sets:
        strategy = qs.get("strategy_name", "unknown")
        query = qs.get("query", "")
        if not query:
            continue

        if cn_only:
            if cn_mode == "filter" and "country:CN" not in query.upper():
                query = f"{query} country:CN"

        print(f"  [xhr_multi_search] {strategy}: {query[:80]}…")

        try:
            result = xhr_search(query, proxy_url=proxy_url, **kwargs)
        except Exception as exc:
            print(f"  [xhr_multi_search] ERROR on {strategy}: {exc}")
            per_strategy_counts[strategy] = 0
            continue

        for patent in result.get("patents", []):
            pub_num = patent.get("publication_number", "")
            if cn_only and cn_mode == "post" and patent.get("country") != "CN":
                continue
            if pub_num and pub_num in seen_pub_nums:
                continue
            if pub_num:
                seen_pub_nums.add(pub_num)
            patent["query_set_name"] = strategy
            all_patents.append(patent)

        per_strategy_counts[strategy] = result.get("total_num_results", 0)

        # Respect max per strategy
        if len(all_patents) >= max_results_per_set * len(query_sets):
            break

    return {
        "total_patents": len(all_patents),
        "patents": all_patents,
        "per_strategy_counts": per_strategy_counts,
        "cn_only": cn_only,
        "cn_mode": cn_mode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search Google Patents via the XHR/query endpoint (no browser needed).",
    )
    parser.add_argument("query", nargs="?", help="Search query string.")
    parser.add_argument("--query-file", help="Path to a JSON file with 'query_sets' array.")
    parser.add_argument("--proxy", default="", help="HTTPS proxy URL, e.g. http://127.0.0.1:7897")
    parser.add_argument("--cn-only", action="store_true", help="Filter results to CN patents only.")
    parser.add_argument("--cn-mode", choices=["filter", "post"], default="filter",
                        help="How to filter CN patents: 'filter' (country:CN in query) or 'post' (client-side filter).")
    parser.add_argument("--page", type=int, default=0, help="Zero-based page number.")
    parser.add_argument("--output", default="", help="Output JSON path (default: stdout).")
    parser.add_argument("--max-results", type=int, default=50, help="Max results per strategy in multi-search.")
    args = parser.parse_args()

    proxy_url = args.proxy or None

    if args.query_file:
        raw = Path(args.query_file).read_text(encoding="utf-8-sig")
        payload = json.loads(raw)
        query_sets = payload.get("query_sets") or payload.get("query_sets_draft", [])
        result = xhr_multi_search(
            query_sets,
            proxy_url=proxy_url,
            max_results_per_set=args.max_results,
            cn_only=args.cn_only,
            cn_mode=args.cn_mode,
        )
    elif args.query:
        if args.cn_only:
            result = xhr_search_cn(args.query, proxy_url=proxy_url, mode=args.cn_mode, page=args.page)
        else:
            result = xhr_search(args.query, proxy_url=proxy_url, page=args.page)
    else:
        parser.error("Provide a query string or --query-file.")

    out = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(out, encoding="utf-8")
        print(f"Saved {len(result.get('patents', []))} patents to {out_path}")
    else:
        print(out)


if __name__ == "__main__":
    main()
