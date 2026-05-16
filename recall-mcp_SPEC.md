# recall-mcp — Project Spec

## What this is

An MCP (Model Context Protocol) server that exposes ReCall's saved-URL corpus as queryable tools inside any MCP-aware client — primarily Claude Desktop, but also Cursor, Claude Code, and any future MCP host. The goal is that I (and anyone else) can ask "what have I saved about X?" from inside Claude Desktop and get real results from my actual ReCall instance, without copy-pasting between apps.

## Why this exists

I built ReCall. I should be able to query it from Claude Desktop while I'm working on anything else. Right now I can't — that's the gap this fills. The project's success criterion is *"runs in my Claude Desktop daily, surviving real use."*

## What this is not

- Not a general-purpose retrieval framework. It's specifically a thin layer over the ReCall backend.
- Not a hosted service. Users self-host by pointing the server at their own ReCall instance.
- Not a UI. There's no web frontend; the MCP host (Claude Desktop, etc.) is the interface.
- Not the flagship. The flagship is a separate multi-agent system; this is one bounded piece.

## Stack

- **Python 3.11+**
- **MCP Python SDK**: `mcp[cli]>=1.25,<2` (do NOT use v2.x — it's in development and will break)
- **HTTP client**: `httpx` (async-native, has timeouts)
- **Package manager**: `uv` (preferred) or stdlib venv
- **Transport**: stdio (default for local servers, what Claude Desktop uses)

## Scope (non-negotiable)

### Four tools

1. **`recall_search(query: str, limit: int = 10) -> str`**
   Search the user's saved URLs by semantic similarity (using ReCall's existing hybrid BM25+vector search). Returns a formatted list of matches with title, URL, summary snippet, and similarity score.

2. **`recall_summarize_url(url: str) -> str`**
   Generate or retrieve a summary for a specific saved URL. If the URL isn't in the user's corpus, returns a clean error. If a cached summary exists, returns that. Otherwise generates one via the backend.

3. **`recall_compare_urls(url_a: str, url_b: str) -> str`**
   Compare two saved URLs — what's similar, what's different. Useful for "I saved two articles on X, what's the substantive difference?"

4. **`recall_list_saved(limit: int = 10, sort: str = "recent") -> str`**
   List recently saved URLs. `sort` accepts `"recent"` or `"popular"` (if popularity data exists).

### Configuration

- One environment variable: `RECALL_API_KEY` (passed as `Authorization: Bearer ...` header to the backend).
- One optional environment variable: `RECALL_BASE_URL` (defaults to the production Railway URL; configurable for local dev).
- No other config. No YAML files, no JSON config, no per-tool settings.

### Error handling

- Every tool body wrapped in try/except.
- On backend timeout (>10s): return `"Error: ReCall backend timed out after 10s"`.
- On backend HTTP error: return `"Error: ReCall returned {status_code}: {message}"`.
- On URL-not-in-corpus: return `"This URL isn't in your saved corpus."` (don't crash).
- **Never raise an unhandled exception.** A crash kills the MCP server process and disconnects all tools mid-conversation.

### Logging

- **Do NOT use `print()` anywhere in tool bodies.** stdio transport uses stdout for protocol messages; a `print` corrupts the JSON-RPC stream and kills the server.
- Use Python's `logging` module configured to write to `stderr`.
- Log at INFO for each tool invocation; DEBUG for full responses.

## ReCall backend API contract

The MCP server calls the ReCall FastAPI backend over HTTP. Endpoints expected:

- `GET /search?q={query}&limit={n}` → `[{url, title, summary, score}, ...]`
- `GET /summarize?url={url}` → `{url, summary}` or `404`
- `POST /compare` body `{url_a, url_b}` → `{similarities: [...], differences: [...]}`
- `GET /saved?limit={n}&sort={recent|popular}` → `[{url, title, saved_at, summary}, ...]`

All authenticated with `Authorization: Bearer {RECALL_API_KEY}`.

If any of these endpoints don't exist yet on the backend, **add them first** as thin wrappers around existing internal logic. Don't redesign the backend; just expose what's needed.

## Build sequence

1. Skeleton: `uv init`, dependencies, one stub tool, `mcp dev` working, repo public on GitHub with one-line README.
2. Real integration: replace stub with real ReCall HTTP calls. Two tools (search + summarize) working end-to-end. Test in `mcp dev` inspector with real saved URLs.
3. Claude Desktop install: `uv run mcp install server.py --name "ReCall"`, restart Desktop, verify real query → real result. Screenshot for README.
4. Two more tools (compare + list) + error handling on all four.
5. README polish.
6. (Stretch) Streaming, PyPI publish.

## README requirements

The README is what people see first. Required structure:

1. **One sentence at the top**: what the project does, in plain English.
2. **Demo GIF or screenshot**: Claude Desktop calling one of the tools with a real result. This is the most important visual.
3. **Install + configure**: exact `uv run mcp install` command plus the env vars.
4. **Tool list**: 4 bullet points, what each tool does, what it returns.
5. **The "why"**: 2–3 sentences. Don't oversell. *"I built this because I wanted my saved URLs available from Claude Desktop while working on anything else. Most public MCP servers are tutorials; this one runs in my Desktop daily."*
6. **Acknowledge alternatives**: link to the official MCP server examples. *"For generic file-reading or web-fetch MCP servers, see the official examples. This one's specifically a thin layer over ReCall."*
7. **License**: MIT.

## Critical don'ts

- **Do NOT pin MCP SDK to v2.x.** Use `>=1.25,<2`.
- **Do NOT use `print()` in tool functions.** Logging to stderr only.
- **Do NOT ship without the Claude Desktop screenshot in the README.** A reviewer landing on the repo should see the tool being called within the first 5 seconds of scrolling.
- **Do NOT add features outside the four-tool scope** in v0.1. New tools wait for v0.2.
- **Do NOT block the event loop** — all backend HTTP calls must be async (use `httpx.AsyncClient`).

## What "done" looks like

A working MCP server installed in my Claude Desktop. I can ask Claude *"What have I saved recently about MCP?"* and get a real answer from my real corpus. The repo is public. The README has a screenshot. Total code: probably 150–250 lines of Python.

## Out-of-scope (future, not v0.1)

- Authentication beyond bearer token (OAuth, etc.).
- Multi-user support (currently single-user, single-corpus).
- A hosted version.
- Streaming responses (stretch, not required).
- PyPI publication (stretch, not required).
- Integration with Cursor, Claude Code, or other MCP hosts (should work automatically since MCP is client-agnostic, but only Claude Desktop is the verification target for v0.1).

## How this fits into the broader plan

This is mini-project #2 in the AI Native Builder Prep Brief v12 (8-week plan targeting Sarvam, Oolka, Emergent). It's the first project I'm building, because of a hot contact at Emergent who values MCP work. Scope decisions for this project should stay inside this SPEC.md — don't broaden them based on what other projects in v12 do. Sync back to v12 happens in a separate planning conversation at week's end, not inside Claude Code while building.

## ReCall backend reference

The backend this server talks to lives at `C:\Users\Ayush Samson D'souza\Desktop\ReCall` on my local machine.

**Deployed backend (Railway)**: `https://railway.com/project/7e524d65-cf27-42e9-8612-f9ac6dc8fb84/service/f3bda033-151b-42db-b5a0-54265e8f4ae7?environmentId=2d19cafa-ecf9-4810-9ada-9250dba337d1` — confirm before wiring real calls.

**Frontend (Vercel, not what we want)**: `https://recall-iota-six.vercel.app/` — this is the React app; the MCP server doesn't talk to this.

Stack: FastAPI + Supabase + pgvector. Hybrid BM25 + vector search using Gemini embeddings (gemini-embedding-001, 768 dimensions).

Live API docs: `https://railway.com/project/7e524d65-cf27-42e9-8612-f9ac6dc8fb84/service/f3bda033-151b-42db-b5a0-54265e8f4ae7?environmentId=2d19cafa-ecf9-4810-9ada-9250dba337d1/docs` (FastAPI auto-generates this; check `/openapi.json` for the raw spec).

To inspect actual endpoint signatures, either ask me to paste relevant route files from the local backend, or fetch the OpenAPI spec from `/openapi.json`.