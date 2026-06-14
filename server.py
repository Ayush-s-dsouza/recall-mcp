import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("recall-mcp")

RECALL_BASE_URL = os.environ.get(
    "RECALL_BASE_URL", "https://recall-production-9941.up.railway.app"
)
RECALL_REFRESH_TOKEN = os.environ.get("RECALL_REFRESH_TOKEN", "")

# Public anon key — safe to embed (it's in the frontend JS bundle).
_SUPABASE_URL = "https://ompfoouatzknuidnccsz.supabase.co"
_SUPABASE_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9tcGZvb3VhdHprbnVpZG5jY3N6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQxMDM4MjUsImV4cCI6MjA4OTY3OTgyNX0"
    ".dbupVBs9RDSTwTW4-2wC8YRMnf7qSKaLuw9giVVV6oI"
)

# Supabase rotates the refresh token on every use, so the value configured at
# install time becomes stale after the first refresh. We cache the latest
# rotated token on disk, keyed to the configured token, so it survives process
# restarts without the user re-entering anything.
_TOKEN_CACHE_PATH = Path.home() / ".recall-mcp" / "token_cache.json"


def _load_cached_refresh_token() -> str:
    try:
        cache = json.loads(_TOKEN_CACHE_PATH.read_text())
        if cache.get("source_refresh_token") == RECALL_REFRESH_TOKEN:
            return cache.get("current_refresh_token") or RECALL_REFRESH_TOKEN
    except (OSError, ValueError):
        pass
    return RECALL_REFRESH_TOKEN


def _save_refresh_token(token: str) -> None:
    try:
        _TOKEN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = _TOKEN_CACHE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps({
            "source_refresh_token": RECALL_REFRESH_TOKEN,
            "current_refresh_token": token,
        }))
        tmp.replace(_TOKEN_CACHE_PATH)
    except OSError:
        log.exception("Failed to persist refreshed token to %s", _TOKEN_CACHE_PATH)


# In-memory token state — refreshed automatically on 401.
_access_token: str = os.environ.get("RECALL_TOKEN", "")
_refresh_token: str = _load_cached_refresh_token()

if not _access_token and not _refresh_token:
    sys.stderr.write(
        "ERROR: Set RECALL_REFRESH_TOKEN (preferred) or RECALL_TOKEN in the config.\n"
        "Get RECALL_REFRESH_TOKEN from DevTools → Application → Local Storage → "
        "sb-*-auth-token → refresh_token\n"
    )
    sys.exit(1)

mcp = FastMCP("ReCall")


# ---------------------------------------------------------------------------
# Token management
# ---------------------------------------------------------------------------

async def _refresh_access_token() -> bool:
    """Exchange the refresh token for a new access token. Returns True on success."""
    global _access_token, _refresh_token
    if not _refresh_token:
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{_SUPABASE_URL}/auth/v1/token?grant_type=refresh_token",
                headers={"apikey": _SUPABASE_ANON_KEY, "Content-Type": "application/json"},
                json={"refresh_token": _refresh_token},
            )
            resp.raise_for_status()
            data = resp.json()
            _access_token = data["access_token"]
            new_refresh_token = data.get("refresh_token", _refresh_token)
            if new_refresh_token != _refresh_token:
                _save_refresh_token(new_refresh_token)
            _refresh_token = new_refresh_token
            log.info("Token refreshed successfully")
            return True
    except Exception:
        log.exception("Token refresh failed")
        return False


async def _post(client: httpx.AsyncClient, url: str, body: dict) -> httpx.Response:
    """POST with automatic token refresh on 401."""
    body = {**body, "token": _access_token}
    resp = await client.post(url, json=body)
    if resp.status_code == 401 and _refresh_token:
        log.info("Got 401 — attempting token refresh")
        if await _refresh_access_token():
            body["token"] = _access_token
            resp = await client.post(url, json=body)
    resp.raise_for_status()
    return resp


# ---------------------------------------------------------------------------
# Formatters — written from observed response shapes
# ---------------------------------------------------------------------------

def _parse_date(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return f"{dt.day} {dt.strftime('%b')} {dt.year}"
    except Exception:
        return iso[:10]


def _fmt_library(data: dict) -> str:
    groups = data.get("library", [])
    if not groups:
        return "Your ReCall library is empty."
    total = sum(g.get("count", 0) for g in groups)
    lines = [f"Your ReCall Library — {total} saves across {len(groups)} tag{'s' if len(groups) != 1 else ''}:\n"]
    for g in groups:
        tag = g.get("tag", "Other")
        count = g.get("count", 0)
        word_count = g.get("word_count", 0)
        summary = g.get("summary", "").strip()
        recent = g.get("recent_titles", [])
        sub_topics = g.get("sub_topics", [])

        wc_str = f"~{word_count // 1000}k words" if word_count >= 1000 else f"{word_count} words"
        lines.append(f"{tag} ({count} saves · {wc_str})")
        if summary:
            lines.append(f"  {summary}")
        if sub_topics:
            topics_str = " · ".join(f"{t['label']} ({t['count']})" for t in sub_topics)
            lines.append(f"  Topics: {topics_str}")
        if recent:
            lines.append(f"  Recent: {' · '.join(recent)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _fmt_ask(data: dict) -> str:
    if data.get("insufficient"):
        return data.get("synthesis", "Not enough saved content to answer that question.")
    synthesis = data.get("synthesis", "").strip()
    sources = data.get("sources", [])
    lines = [synthesis, ""]
    if sources:
        lines.append("Sources:")
        for i, s in enumerate(sources, 1):
            title = s.get("title", "Untitled").strip().replace("\n", " ")
            url = s.get("url", "")
            tag = s.get("tag", "")
            meta = f" [{tag}]" if tag else ""
            lines.append(f"{i}. {title}{meta}")
            lines.append(f"   {url}")
    return "\n".join(lines)


def _fmt_search(query: str, data: dict) -> str:
    results = data.get("results", [])
    if not results:
        return f"No saved URLs found matching \"{query}\"."
    lines = [f"Results for \"{query}\" — {len(results)} match{'es' if len(results) != 1 else ''}:\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "Untitled").strip().replace("\n", " ")
        url = r.get("url", "")
        tag = r.get("tag", "")
        pct = round(r.get("similarity", 0) * 100)
        date = _parse_date(r.get("created_at", ""))
        excerpt = r.get("excerpt", "").strip().replace("\n", " ")

        meta_parts = [p for p in [tag, date, f"{pct}% match"] if p]
        lines.append(f"{i}. {title}")
        lines.append(f"   {' · '.join(meta_parts)}")
        lines.append(f"   {url}")
        if excerpt:
            snip = excerpt[:200] + ("…" if len(excerpt) > 200 else "")
            lines.append(f"   \"{snip}\"")
        lines.append("")
    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def recall_search(query: str) -> str:
    """Search your saved URLs by semantic similarity."""
    log.info("recall_search called: query=%r", query)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await _post(client, f"{RECALL_BASE_URL}/search", {"query": query})
            data = resp.json()
            log.debug("recall_search raw: %s", data)
            return _fmt_search(query, data)
    except httpx.TimeoutException:
        return "Error: ReCall backend timed out after 30s"
    except httpx.HTTPStatusError as e:
        return f"Error: ReCall returned {e.response.status_code}: {e.response.text}"
    except Exception as e:
        log.exception("recall_search unexpected error")
        return f"Error: {e}"


@mcp.tool()
async def recall_ask(question: str) -> str:
    """Ask a question answered from your saved URLs (RAG Q&A over your corpus)."""
    log.info("recall_ask called: question=%r", question)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await _post(client, f"{RECALL_BASE_URL}/ask", {"query": question})
            data = resp.json()
            log.debug("recall_ask raw: %s", data)
            return _fmt_ask(data)
    except httpx.TimeoutException:
        return "Error: ReCall backend timed out after 30s"
    except httpx.HTTPStatusError as e:
        return f"Error: ReCall returned {e.response.status_code}: {e.response.text}"
    except Exception as e:
        log.exception("recall_ask unexpected error")
        return f"Error: {e}"


@mcp.tool()
async def recall_list_saved() -> str:
    """List all URLs saved in your ReCall library."""
    log.info("recall_list_saved called")
    try:
        # /library makes sequential Gemini calls per tag group — needs a longer timeout.
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await _post(client, f"{RECALL_BASE_URL}/library", {})
            data = resp.json()
            log.debug("recall_list_saved raw: %s", data)
            return _fmt_library(data)
    except httpx.TimeoutException:
        return "Error: ReCall backend timed out after 90s (library generates AI summaries per tag — try again)"
    except httpx.HTTPStatusError as e:
        return f"Error: ReCall returned {e.response.status_code}: {e.response.text}"
    except Exception as e:
        log.exception("recall_list_saved unexpected error")
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run()
