# CLAUDE.md — Lexcom Sales Agent

## Project Overview

Two Python packages powering Lexcom's inside sales workflow:

1. **Sales Agent** (`sales_agent/`) — MCP server with 6 composite sales tools that orchestrate ConnectWise + TD Synnex data. Customer profiling, upsell suggestions, price comparison, quote building, renewal tracking, and opportunity enrichment.

2. **TD Synnex StreamOne Ion Adapter** (`tdsynnex/`) — Full StreamOne Ion V3 API client + 15-tool MCP server for direct distributor operations. Auth, customers, catalog, orders, subscriptions, carts, provisioning.

## Architecture

```
                    ┌─────────────────────────────┐
                    │  Claude Code (orchestrator)  │
                    └──────────┬──────────────────┘
                               │ MCP (stdio)
              ┌────────────────┼────────────────┐
              ▼                ▼                 ▼
   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
   │ Sales Agent   │  │ TD Synnex    │  │ CW MCP       │
   │ MCP Server    │  │ MCP Server   │  │ (separate    │
   │ (6 tools)     │  │ (15 tools)   │  │  repo)       │
   └──────┬───────┘  └──────────────┘  └──────────────┘
          │
    ┌─────┴─────┐
    ▼           ▼
 CW REST    TDSynnex
 API        Client
```

- **Sales Agent MCP**: Composite tools — calls CW REST API directly + imports TDSynnexClient
- **TD Synnex MCP**: Direct distributor operations for when Claude needs raw API access
- **CW MCP** (separate repo: jryan5150/cw-mcp-server): 73-tool CW server for direct CW operations
- **Ollama**: On Jetson, optional — reserved for future AI-powered product matching

## Sales Agent Tools

| Tool | What It Does |
|------|-------------|
| `customer_profile` | CW company + contacts + agreements + configs + tickets + TDSynnex subscriptions in one view |
| `suggest_upsells` | Analyzes current stack, suggests gaps from TD Synnex catalog |
| `price_comparison` | TD Synnex cost vs CW catalog sell price — margin analysis |
| `build_quote` | Creates a TD Synnex cart as a draft quote (does NOT checkout) |
| `renewal_radar` | Upcoming CW agreement expirations + TD Synnex subscription renewals |
| `opportunity_enrichment` | Enriches a CW opportunity with customer context + catalog matches |

## Current State

### Built:
- `sales_agent/clients/connectwise.py` — Async CW client (mirrors auth from cw-mcp-server)
- `sales_agent/workflows/` — All 6 workflow modules
- `sales_agent/mcp/server.py` — MCP server exposing composite tools
- `tdsynnex/client/streamone.py` — Full StreamOne Ion V3 client
- `tdsynnex/mcp/server.py` — 15-tool MCP server for direct distributor ops

### Next Steps:
1. Fill `.env` with CW + TD Synnex credentials
2. Test sales agent MCP server: `python -m sales_agent.mcp.server`
3. Test TD Synnex MCP server: `python -m tdsynnex.mcp.server`
4. Add both to Claude Code `.mcp.json`
5. Run `customer_profile` against a real CW company
6. Run `renewal_radar` to find upcoming renewals
7. Test `build_quote` flow end-to-end

### Future:
- Ollama-powered product matching (keyword extraction → smarter catalog search)
- CW ↔ TD Synnex customer ID mapping table (SQLite)
- Automated renewal outreach alerts
- Quote-to-CW-opportunity pipeline (auto-create opportunity from quote)

## Context

### Why this exists
Lexcom's inside sales workflow crosses two systems: ConnectWise (PSA — customer data, agreements, opportunities) and TD Synnex StreamOne (distributor — catalog, pricing, ordering). The sales agent bridges them so Claude can do composite operations in a single conversation.

### Adjacent systems
- **CW MCP Server** (jryan5150/cw-mcp-server) — 73-tool TypeScript MCP server for direct CW operations
- **Lexcom Command Center** (jryan5150/lexcom-command-center) — Time reconstruction engine
- **SUBSCORE / WEaveField** — Separate ventures, different repos

## Code Style
- Python 3.10+, type hints everywhere
- Pydantic models for config
- async/await throughout (httpx, MCP SDK)
- No agent frameworks — direct API calls + MCP tools
- Workflows are pure async functions, MCP server is thin dispatch

## Red Lines
- No credentials in code — `.env` only
- `build_quote` creates draft carts — never auto-checkout without human confirmation
- TD Synnex refresh tokens rotate on use — the client handles this, but don't store stale tokens
- Keep workflows stateless — all state lives in CW and TD Synnex
