import logging
import os

import httpx
from mcp.server.fastmcp import FastMCP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=__import__("sys").stderr,
)
log = logging.getLogger("recall-mcp")

RECALL_BASE_URL = os.environ.get("RECALL_BASE_URL", "https://recall-backend.railway.app")
RECALL_API_KEY = os.environ.get("RECALL_API_KEY", "")

mcp = FastMCP("ReCall")


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {RECALL_API_KEY}"}


# ---------------------------------------------------------------------------
# Block 1 stub — hardcoded response, real HTTP call wired in Block 2
# ---------------------------------------------------------------------------

@mcp.tool()
async def recall_search(query: str, limit: int = 10) -> str:
    """Search your saved URLs by semantic similarity."""
    log.info("recall_search called: query=%r limit=%d", query, limit)
    # Stub: return hardcoded data so the MCP inspector can verify the tool works.
    stub_results = [
        {
            "title": "Model Context Protocol — Introduction",
            "url": "https://modelcontextprotocol.io/introduction",
            "summary": "The official MCP spec and motivation; explains why a shared protocol between LLMs and tools matters.",
            "score": 0.97,
        },
        {
            "title": "Building MCP servers with Python",
            "url": "https://github.com/anthropics/mcp-python",
            "summary": "Python SDK for building MCP servers using FastMCP or low-level primitives.",
            "score": 0.91,
        },
    ]
    lines = [f"Results for '{query}' (stub — real backend not yet wired):\n"]
    for i, r in enumerate(stub_results[:limit], 1):
        lines.append(
            f"{i}. [{r['title']}]({r['url']})\n"
            f"   Score: {r['score']:.2f} | {r['summary']}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Remaining tools — stubs, wired in Block 4
# ---------------------------------------------------------------------------

@mcp.tool()
async def recall_summarize_url(url: str) -> str:
    """Generate or retrieve a summary for a specific saved URL."""
    log.info("recall_summarize_url called: url=%r", url)
    return "Not yet implemented — coming in Block 2."


@mcp.tool()
async def recall_compare_urls(url_a: str, url_b: str) -> str:
    """Compare two saved URLs — similarities and differences."""
    log.info("recall_compare_urls called: url_a=%r url_b=%r", url_a, url_b)
    return "Not yet implemented — coming in Block 4."


@mcp.tool()
async def recall_list_saved(limit: int = 10, sort: str = "recent") -> str:
    """List recently or popularly saved URLs from your corpus."""
    log.info("recall_list_saved called: limit=%d sort=%r", limit, sort)
    return "Not yet implemented — coming in Block 4."


if __name__ == "__main__":
    mcp.run()
