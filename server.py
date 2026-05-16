import json
import logging
import os
import sys

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
RECALL_TOKEN = os.environ.get("RECALL_TOKEN", "")

if not RECALL_TOKEN:
    sys.stderr.write(
        "ERROR: RECALL_TOKEN environment variable is not set. "
        "Export it before starting the server.\n"
    )
    sys.exit(1)

mcp = FastMCP("ReCall")


@mcp.tool()
async def recall_search(query: str) -> str:
    """Search your saved URLs by semantic similarity."""
    log.info("recall_search called: query=%r", query)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{RECALL_BASE_URL}/search",
                json={"query": query, "token": RECALL_TOKEN},
            )
            resp.raise_for_status()
            data = resp.json()
            log.debug("recall_search raw: %s", data)
            # Formatter refined after first real response — returning raw JSON for now.
            return json.dumps(data, indent=2)
    except httpx.TimeoutException:
        return "Error: ReCall backend timed out after 10s"
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
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{RECALL_BASE_URL}/ask",
                json={"query": question, "token": RECALL_TOKEN},
            )
            resp.raise_for_status()
            data = resp.json()
            log.debug("recall_ask raw: %s", data)
            return json.dumps(data, indent=2)
    except httpx.TimeoutException:
        return "Error: ReCall backend timed out after 10s"
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
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{RECALL_BASE_URL}/library",
                json={"token": RECALL_TOKEN},
            )
            resp.raise_for_status()
            data = resp.json()
            log.debug("recall_list_saved raw: %s", data)
            return json.dumps(data, indent=2)
    except httpx.TimeoutException:
        return "Error: ReCall backend timed out after 10s"
    except httpx.HTTPStatusError as e:
        return f"Error: ReCall returned {e.response.status_code}: {e.response.text}"
    except Exception as e:
        log.exception("recall_list_saved unexpected error")
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run()
