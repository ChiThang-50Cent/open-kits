#!/usr/bin/env python3

import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from ddgs import DDGS


SEARX_SPACE_INSTANCES_URL = "https://searx.space/instances.json"
SEARXNG_INSTANCES = [
    "https://paulgo.io",
    "https://search.inetol.net",
    "https://searx.be",
    "https://search.sapti.me",
]
SEARXNG_INSTANCE_CACHE_TTL_SECONDS = 600

TRACKING_PARAMS = {"gclid", "fbclid", "msclkid", "ref"}

_searxng_rotation_lock = threading.Lock()
_searxng_rotation_counter = 0
_searxng_instances_cache_lock = threading.Lock()
_searxng_instances_cache = {
    "items": list(SEARXNG_INSTANCES),
    "fetched_at": 0.0,
}


def _extract_instance_urls(entry):
    urls = []
    if isinstance(entry, str):
        urls.append(entry)
    elif isinstance(entry, dict):
        direct = entry.get("url")
        if isinstance(direct, str):
            urls.append(direct)

        many = entry.get("urls")
        if isinstance(many, list):
            for value in many:
                if isinstance(value, str):
                    urls.append(value)
    return urls


def _extract_https_instances(payload):
    if isinstance(payload, dict):
        raw_instances = payload.get("instances", [])
    elif isinstance(payload, list):
        raw_instances = payload
    else:
        raw_instances = []

    seen = set()
    items = []
    for entry in raw_instances:
        for url in _extract_instance_urls(entry):
            if not url.startswith("https://"):
                continue
            cleaned = url.rstrip("/")
            if cleaned in seen:
                continue
            seen.add(cleaned)
            items.append(cleaned)
    return items


def resolve_searxng_instances(timeout):
    now = time.time()
    with _searxng_instances_cache_lock:
        cached = list(_searxng_instances_cache["items"])
        fetched_at = _searxng_instances_cache["fetched_at"]
        if cached and now - fetched_at < SEARXNG_INSTANCE_CACHE_TTL_SECONDS:
            return cached

    request = Request(
        SEARX_SPACE_INSTANCES_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "opencode-ddgs-search/1.0",
        },
    )
    try:
        with urlopen(request, timeout=min(timeout, 5)) as response:
            body = response.read().decode("utf-8", errors="replace")
        payload = json.loads(body)
        items = _extract_https_instances(payload)
        if items:
            with _searxng_instances_cache_lock:
                _searxng_instances_cache["items"] = list(items)
                _searxng_instances_cache["fetched_at"] = now
            return items
    except Exception:
        pass

    with _searxng_instances_cache_lock:
        fallback = list(_searxng_instances_cache["items"] or SEARXNG_INSTANCES)
        _searxng_instances_cache["items"] = list(fallback)
        if _searxng_instances_cache["fetched_at"] <= 0:
            _searxng_instances_cache["fetched_at"] = now
    return fallback


def classify_error(err, provider):
    msg = str(err).lower()
    if "timeout" in msg or "timed out" in msg:
        return ("TIMEOUT", True)
    if "connect" in msg or "connection" in msg or "network" in msg:
        return ("NETWORK_ERROR", True)
    if "rate" in msg or "429" in msg or "too many" in msg:
        return ("RATE_LIMIT", True)
    if "403" in msg or "blocked" in msg or "forbidden" in msg:
        return ("BLOCKED", False)
    if provider == "searxng":
        return ("SEARXNG_ERROR", True)
    return ("DDGS_ERROR", True)


def canonicalize_url(url):
    if not url:
        return None
    try:
        parsed = urlsplit(url)
    except Exception:
        return None

    scheme = (parsed.scheme or "").lower()
    netloc = parsed.netloc or ""
    path = parsed.path or ""

    if "@" in netloc:
        auth, hostport = netloc.rsplit("@", 1)
        auth += "@"
    else:
        auth = ""
        hostport = netloc

    if ":" in hostport:
        host, port = hostport.rsplit(":", 1)
    else:
        host, port = hostport, ""

    host = host.lower()
    if (scheme == "http" and port == "80") or (scheme == "https" and port == "443"):
        port = ""

    rebuilt_netloc = f"{auth}{host}" + (f":{port}" if port else "")

    if path == "/":
        path = "/"

    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    filtered_pairs = []
    for key, value in query_pairs:
        lower_key = key.lower()
        if lower_key.startswith("utm_") or lower_key in TRACKING_PARAMS:
            continue
        filtered_pairs.append((key, value))

    query = urlencode(filtered_pairs, doseq=True)
    return urlunsplit((scheme, rebuilt_netloc, path, query, ""))


def normalize_url_source(url):
    try:
        return urlsplit(url).hostname or "unknown"
    except Exception:
        return "unknown"


def normalize_ddgs_text(items, snippet_length):
    normalized = []
    for item in items or []:
        url = item.get("href") or item.get("url")
        if not url:
            continue
        title = (item.get("title") or "").strip() or "(untitled)"
        snippet = (item.get("body") or item.get("content") or "").strip()

        entry = {
            "title": title,
            "url": url,
            "snippet": snippet[:snippet_length],
            "source": normalize_url_source(url),
        }
        date = item.get("published") or item.get("date")
        if date:
            entry["date"] = str(date)
        normalized.append(entry)
    return normalized


def normalize_ddgs_news(items, snippet_length):
    normalized = []
    for item in items or []:
        url = item.get("url") or item.get("href")
        if not url:
            continue
        title = (item.get("title") or "").strip() or "(untitled)"
        snippet = (item.get("body") or item.get("excerpt") or "").strip()

        entry = {
            "title": title,
            "url": url,
            "snippet": snippet[:snippet_length],
            "source": normalize_url_source(url),
        }
        date = item.get("date") or item.get("published")
        if date:
            entry["date"] = str(date)
        publisher = item.get("source") or item.get("publisher")
        if publisher:
            entry["publisher"] = str(publisher)
        normalized.append(entry)
    return normalized


def normalize_searxng(items, search_type, snippet_length):
    normalized = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        title = item.get("title")
        if not url or not title:
            continue

        snippet = (
            item.get("content") or item.get("snippet") or item.get("description") or ""
        )

        entry = {
            "title": str(title).strip() or "(untitled)",
            "url": str(url),
            "snippet": str(snippet).strip()[:snippet_length],
            "source": normalize_url_source(str(url)),
        }

        date = item.get("publishedDate") or item.get("published") or item.get("date")
        if date:
            entry["date"] = str(date)

        if search_type == "news":
            publisher = item.get("engine") or item.get("source")
            if publisher:
                entry["publisher"] = str(publisher)

        normalized.append(entry)
    return normalized


def make_provider_ok(items, latency_ms):
    return {
        "ok": True,
        "items": items,
        "error": None,
        "latency_ms": latency_ms,
    }


def make_provider_error(code, message, retryable, latency_ms):
    return {
        "ok": False,
        "items": [],
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable,
        },
        "latency_ms": latency_ms,
    }


def search_ddgs(args):
    started = time.time()
    try:
        client = DDGS(timeout=args.timeout)
        common = dict(
            query=args.query,
            region=args.region,
            safesearch=args.safesearch,
            timelimit=args.timelimit,
            max_results=args.max_results,
            page=args.page,
            backend=args.backend,
        )

        if args.search_type == "news":
            results = client.news(**common)
            items = normalize_ddgs_news(results, args.snippet_length)
        else:
            results = client.text(**common)
            items = normalize_ddgs_text(results, args.snippet_length)

        latency_ms = int((time.time() - started) * 1000)
        return make_provider_ok(items, latency_ms)
    except Exception as err:
        code, retryable = classify_error(err, "ddgs")
        latency_ms = int((time.time() - started) * 1000)
        return make_provider_error(code, str(err), retryable, latency_ms)


def next_searxng_start_index(size):
    global _searxng_rotation_counter
    if size <= 0:
        return 0
    with _searxng_rotation_lock:
        idx = _searxng_rotation_counter % size
        _searxng_rotation_counter += 1
    return idx


def build_searxng_url(base, args):
    params = {
        "q": args.query,
        "format": "json",
        "pageno": args.page,
    }

    if args.search_type == "news":
        params["categories"] = "news"

    safesearch_map = {"off": 0, "moderate": 1, "on": 2}
    params["safesearch"] = safesearch_map.get(args.safesearch, 1)

    if args.timelimit:
        params["time_range"] = args.timelimit

    if args.region:
        parts = args.region.split("-")
        if parts:
            params["language"] = parts[-1]

    return f"{base.rstrip('/')}/search?{urlencode(params)}"


def search_searxng(args):
    started = time.time()
    instances = resolve_searxng_instances(args.timeout)
    if not instances:
        latency_ms = int((time.time() - started) * 1000)
        return make_provider_error(
            "SEARXNG_ERROR", "No SearXNG instances configured", True, latency_ms
        )

    probe_timeout = min(args.timeout, 3)
    max_probes = min(2, len(instances))
    first = next_searxng_start_index(len(instances))

    last_error = None
    for i in range(max_probes):
        idx = (first + i) % len(instances)
        base_url = instances[idx]
        url = build_searxng_url(base_url, args)
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "opencode-ddgs-search/1.0",
            },
        )

        try:
            with urlopen(request, timeout=probe_timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
            payload = json.loads(body)
            items = normalize_searxng(
                payload.get("results", []), args.search_type, args.snippet_length
            )
            latency_ms = int((time.time() - started) * 1000)
            return make_provider_ok(items, latency_ms)
        except Exception as err:
            last_error = err

    code, retryable = classify_error(
        last_error or Exception("Unknown SearXNG failure"), "searxng"
    )
    latency_ms = int((time.time() - started) * 1000)
    return make_provider_error(code, str(last_error), retryable, latency_ms)


def metadata_richness(item):
    score = len(item.get("snippet", ""))
    if item.get("date"):
        score += 10
    if item.get("publisher"):
        score += 10
    return score


def merge_results(ddgs_items, searxng_items, max_results):
    merged = []
    seen_index = {}
    max_len = max(len(ddgs_items), len(searxng_items))

    interleaved = []
    for i in range(max_len):
        if i < len(ddgs_items):
            interleaved.append(("ddgs", ddgs_items[i]))
        if i < len(searxng_items):
            interleaved.append(("searxng", searxng_items[i]))

    for provider, item in interleaved:
        url = item.get("url")
        if not url:
            continue
        canonical = canonicalize_url(url)
        key = canonical if canonical else f"raw:{url}"

        current_idx = seen_index.get(key)
        if current_idx is None:
            seen_index[key] = len(merged)
            merged.append((provider, item))
            continue

        _, existing = merged[current_idx]
        existing_score = metadata_richness(existing)
        incoming_score = metadata_richness(item)

        if incoming_score > existing_score:
            merged[current_idx] = (provider, item)
        elif incoming_score == existing_score:
            current_provider = merged[current_idx][0]
            if current_provider != "ddgs" and provider == "ddgs":
                merged[current_idx] = (provider, item)

    return [item for _, item in merged[:max_results]]


def collapse_provider_errors(ddgs_error, searxng_error):
    precedence = {
        "RATE_LIMIT": 0,
        "NETWORK_ERROR": 1,
        "TIMEOUT": 2,
        "DDGS_ERROR": 3,
        "SEARXNG_ERROR": 3,
        "UNKNOWN": 4,
    }

    candidates = []
    if ddgs_error:
        candidates.append(("ddgs", ddgs_error))
    if searxng_error:
        candidates.append(("searxng", searxng_error))

    candidates.sort(
        key=lambda x: (precedence.get(x[1]["code"], 4), 0 if x[0] == "ddgs" else 1)
    )
    chosen = (
        candidates[0][1]
        if candidates
        else {"code": "UNKNOWN", "message": "Unknown", "retryable": True}
    )
    retryable = any(err["retryable"] for _, err in candidates) if candidates else True

    ddgs_code = ddgs_error["code"] if ddgs_error else "NONE"
    searxng_code = searxng_error["code"] if searxng_error else "NONE"
    return {
        "code": chosen["code"],
        "message": f"{chosen['message']} (ddgs={ddgs_code}, searxng={searxng_code})",
        "retryable": retryable,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Hybrid DDGS + SearXNG web search helper"
    )
    parser.add_argument("--query", required=True)
    parser.add_argument("--search-type", choices=["text", "news"], default="text")
    parser.add_argument("--region", default="vn-vi")
    parser.add_argument(
        "--safesearch", choices=["on", "moderate", "off"], default="moderate"
    )
    parser.add_argument("--timelimit", choices=["d", "w", "m", "y"], default=None)
    parser.add_argument("--backend", default="auto")
    parser.add_argument("--max-results", type=int, default=8)
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=8)
    parser.add_argument("--snippet-length", type=int, default=500)
    args = parser.parse_args()

    with ThreadPoolExecutor(max_workers=2) as executor:
        ddgs_future = executor.submit(search_ddgs, args)
        searxng_future = executor.submit(search_searxng, args)
        ddgs_result = ddgs_future.result()
        searxng_result = searxng_future.result()

    ddgs_items = ddgs_result["items"] if ddgs_result["ok"] else []
    searxng_items = searxng_result["items"] if searxng_result["ok"] else []

    if not ddgs_items and not searxng_items:
        error = collapse_provider_errors(
            ddgs_result.get("error"), searxng_result.get("error")
        )
        print(
            json.dumps(
                {
                    "ok": False,
                    "query": args.query,
                    "results": [],
                    "error": error,
                },
                ensure_ascii=False,
            )
        )
        return

    merged = merge_results(ddgs_items, searxng_items, args.max_results)
    payload = {
        "ok": True,
        "query": args.query,
        "search_type": args.search_type,
        "results": merged,
        "meta": {
            "total_returned": len(merged),
            "region": args.region,
            "safesearch": args.safesearch,
            "timelimit": args.timelimit,
            "backend": "hybrid",
            "page": args.page,
        },
    }
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
